# ---------- FILE: cogs/scoring.py ----------
import discord
from discord.ext import commands
from discord import app_commands
from database import SessionLocal, Name, ScoreHistory
from cogs.utilities import split_long_message
import matplotlib.pyplot as plt
import matplotlib
import seaborn as sns
from io import BytesIO
from tabulate import tabulate

matplotlib.use("Agg")
sns.set_theme()


class ScoringCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def is_admin(self, interaction):
        return interaction.user.guild_permissions.administrator

    # ---------- Helper function for score rule ----------
    def update_score(self, session, name_obj: Name, new_val: int, category: str):
        """
        Updates the score following your rule:
        - First score is permanent (treat 0 or None as "no previous").
        - Later scores: only add positive difference.
        - Ignore subtractions.
        Returns: (new_total, diff, updated_bool)
        """
        if category == "kill":
            current = name_obj.kill_score
        else:
            current = name_obj.vs_score

        # Treat 0 or None as "no previous score"
        if current is None or current == 0:
            if category == "kill":
                name_obj.kill_score = new_val
            else:
                name_obj.vs_score = new_val
            session.add(ScoreHistory(name=name_obj, category=category, value=new_val))
            return new_val, new_val, True

        if new_val > current:
            diff = new_val - current
            if category == "kill":
                name_obj.kill_score = new_val
            else:
                name_obj.vs_score = new_val
            session.add(ScoreHistory(name=name_obj, category=category, value=new_val))
            return new_val, diff, True

        return current, 0, False

    # ---------- Add/Update Score ----------
    @app_commands.command(name="addscore", description="Add or update a score for a name (Admin only)")
    @app_commands.describe(category="Choose score type", name="Name to track", value="Value to add/update", showdiff="Show difference?")
    @app_commands.choices(category=[
        app_commands.Choice(name="Kill Score", value="kill"),
        app_commands.Choice(name="VS Score", value="vs")
    ])
    @app_commands.choices(showdiff=[
        app_commands.Choice(name="Yes", value="yes"),
        app_commands.Choice(name="No", value="no")
    ])
    async def addscore(self, interaction: discord.Interaction, category: app_commands.Choice[str], name: str, value: int, showdiff: app_commands.Choice[str] = None):
        if not await self.is_admin(interaction):
            await interaction.response.send_message("❌ Admins only.", ephemeral=True)
            return

        session = SessionLocal()
        try:
            obj = session.query(Name).filter_by(name=name).first()
            if not obj:
                obj = Name(name=name)
                session.add(obj)
                session.commit()
                session.refresh(obj)

            new_total, diff, updated = self.update_score(session, obj, value, category.value)
            session.commit()

            emoji = "🔥" if category.value == "kill" else "🛠"
            if updated:
                if showdiff and showdiff.value == "yes":
                    await interaction.response.send_message(f"✅ {category.name} updated: {name} = {new_total:,} (+{diff:,}) {emoji}", ephemeral=True)
                else:
                    await interaction.response.send_message(f"✅ {category.name} updated: {name} = {new_total:,} {emoji}", ephemeral=True)
            else:
                current = obj.kill_score if category.value == "kill" else obj.vs_score
                await interaction.response.send_message(f"⚠️ Ignored update: {name} already has a higher or equal score ({current:,}).", ephemeral=True)
        finally:
            session.close()

    # ---------- Remove Name ----------
    @app_commands.command(name="removename", description="Remove a tracked name (Admin only)")
    async def removename(self, interaction, name: str):
        if not await self.is_admin(interaction):
            await interaction.response.send_message("❌ Admins only.", ephemeral=True)
            return
        session = SessionLocal()
        try:
            obj = session.query(Name).filter_by(name=name).first()
            if not obj:
                await interaction.response.send_message("⚠️ Name not found.", ephemeral=True)
                return
            session.delete(obj)
            session.commit()
            await interaction.response.send_message(f"✅ Removed {name}.", ephemeral=True)
        finally:
            session.close()

    # ---------- Show Scores ----------
    @app_commands.command(name="showscores", description="Show scores as table or graph")
    @app_commands.describe(category="Choose score type", mode="Display as table or graph", showdiff="Show difference?")
    @app_commands.choices(category=[
        app_commands.Choice(name="Kill Score", value="kill"),
        app_commands.Choice(name="VS Score", value="vs")
    ])
    @app_commands.choices(mode=[
        app_commands.Choice(name="Table", value="table"),
        app_commands.Choice(name="Graph", value="graph")
    ])
    @app_commands.choices(showdiff=[
        app_commands.Choice(name="Yes", value="yes"),
        app_commands.Choice(name="No", value="no")
    ])
    async def showscores(self, interaction, category: app_commands.Choice[str], mode: app_commands.Choice[str], showdiff: app_commands.Choice[str] = None):
        session = SessionLocal()
        try:
            names = session.query(Name).all()
            if not names:
                await interaction.response.send_message("⚠️ No scores available.", ephemeral=True)
                return

            # Build dictionary {name: value}
            data = {}
            for n in names:
                val = n.kill_score if category.value == "kill" else n.vs_score
                data[n.name] = val
            sorted_data = dict(sorted(data.items(), key=lambda x: x[1] if x[1] is not None else 0, reverse=True))
            emoji = "🔥" if category.value == "kill" else "🛠"

            if mode.value == "table":
                table_rows = []
                for i, (nm, val) in enumerate(sorted_data.items(), start=1):
                    # find previous value (if any)
                    name_obj = session.query(Name).filter_by(name=nm).first()
                    prev_hist = session.query(ScoreHistory).filter_by(name_id=name_obj.id, category=category.value).order_by(ScoreHistory.timestamp.desc()).offset(1).first()
                    prev_val = prev_hist.value if prev_hist else 0
                    diff = val - prev_val
                    if showdiff and showdiff.value == "yes":
                        table_rows.append([f"#{i}", nm, f"{val:,}", f"{diff:+,}", emoji])
                    else:
                        table_rows.append([f"#{i}", nm, f"{val:,}", "", emoji])

                headers = ["Rank", "Name", "Score", ("Δ" if (showdiff and showdiff.value == "yes") else ""), ""]
                table_str = tabulate(table_rows, headers=headers)
                embed = discord.Embed(title=f"{category.name} Table", description=f"```{table_str}```", color=0x00ffcc)
                await interaction.response.send_message(embed=embed)
            else:
                fig, ax = plt.subplots()
                # simple horizontal rotation for readability
                ax.bar(sorted_data.keys(), sorted_data.values())
                ax.set_ylabel("Score")
                ax.set_title(f"{category.name}")
                plt.xticks(rotation=45, ha="right")
                buf = BytesIO()
                plt.tight_layout()
                plt.savefig(buf, format="png")
                buf.seek(0)
                await interaction.response.send_message(file=discord.File(buf, filename="graph.png"))
        finally:
            session.close()

    # ---------- Leaderboard ----------
    @app_commands.command(name="leaderboard", description="Show leaderboard for a category")
    @app_commands.describe(category="Choose score type", top="Optional top N", showdiff="Show difference?")
    @app_commands.choices(category=[
        app_commands.Choice(name="Kill Score", value="kill"),
        app_commands.Choice(name="VS Score", value="vs")
    ])
    @app_commands.choices(showdiff=[
        app_commands.Choice(name="Yes", value="yes"),
        app_commands.Choice(name="No", value="no")
    ])
    async def leaderboard(self, interaction, category: app_commands.Choice[str], top: int = None, showdiff: app_commands.Choice[str] = None):
        session = SessionLocal()
        try:
            names = session.query(Name).all()
            if not names:
                await interaction.response.send_message("⚠️ No scores available.", ephemeral=True)
                return

            data = {}
            for n in names:
                val = n.kill_score if category.value == "kill" else n.vs_score
                data[n.name] = val
            sorted_data = sorted(data.items(), key=lambda x: x[1] if x[1] is not None else 0, reverse=True)
            if top:
                sorted_data = sorted_data[:top]

            emoji = "🔥" if category.value == "kill" else "🛠"
            embed = discord.Embed(title=f"{category.name} Leaderboard", color=0xffa500)

            for i, (nm, val) in enumerate(sorted_data, start=1):
                field_text = f"{val:,} {emoji}"
                if showdiff and showdiff.value == "yes":
                    name_obj = session.query(Name).filter_by(name=nm).first()
                    prev_hist = session.query(ScoreHistory).filter_by(name_id=name_obj.id, category=category.value).order_by(ScoreHistory.timestamp.desc()).offset(1).first()
                    if prev_hist:
                        diff = val - prev_hist.value
                        if diff > 0:
                            field_text += f" ({diff:+,})"
                embed.add_field(name=f"#{i} {nm}", value=field_text, inline=False)

            await interaction.response.send_message(embed=embed)
        finally:
            session.close()

    # ---------- (Text) Export ----------
    @app_commands.command(name="export", description="Export scores (text)")
    @app_commands.describe(category="Choose score type", showdiff="Show difference?")
    @app_commands.choices(category=[
        app_commands.Choice(name="Kill Score", value="kill"),
        app_commands.Choice(name="VS Score", value="vs")
    ])
    @app_commands.choices(showdiff=[
        app_commands.Choice(name="Yes", value="yes"),
        app_commands.Choice(name="No", value="no")
    ])
    async def export(self, interaction: discord.Interaction, category: app_commands.Choice[str], showdiff: app_commands.Choice[str] = None):
        session = SessionLocal()
        try:
            names = session.query(Name).all()
            if not names:
                await interaction.response.send_message("⚠️ No scores found.", ephemeral=True)
                return

            lines = []
            for n in names:
                val = n.kill_score if category.value == "kill" else n.vs_score
                line = f"{n.name}:{val}"
                if showdiff and showdiff.value == "yes":
                    prev_hist = session.query(ScoreHistory).filter_by(name_id=n.id, category=category.value).order_by(ScoreHistory.timestamp.desc()).offset(1).first()
                    if prev_hist:
                        latest_hist = session.query(ScoreHistory).filter_by(name_id=n.id, category=category.value).order_by(ScoreHistory.timestamp.desc()).first()
                        diff = latest_hist.value - prev_hist.value
                        if diff > 0:
                            line += f" (Δ+{diff})"
                lines.append(line)

            chunks = split_long_message("\n".join(lines))
            # send first chunk as response, others as followups
            await interaction.response.send_message(chunks[0])
            for c in chunks[1:]:
                await interaction.followup.send(c)
        finally:
            session.close()

    # ---------- (Text) Import ----------
    @app_commands.command(name="import", description="Import scores (text)")
    @app_commands.describe(data="Paste exported scores", category="Choose score type", showdiff="Expect diff column?")
    @app_commands.choices(category=[
        app_commands.Choice(name="Kill Score", value="kill"),
        app_commands.Choice(name="VS Score", value="vs")
    ])
    @app_commands.choices(showdiff=[
        app_commands.Choice(name="Yes", value="yes"),
        app_commands.Choice(name="No", value="no")
    ])
    async def import_scores(self, interaction: discord.Interaction, data: str, category: app_commands.Choice[str], showdiff: app_commands.Choice[str] = None):
        session = SessionLocal()
        try:
            lines = data.splitlines()
            updated = 0
            ignored = 0
            for line in lines:
                if ":" not in line:
                    continue
                parts = line.split(":")
                nm = parts[0].strip()
                score_part = parts[1].strip()

                # If diff appended like "123 (Δ+45)", strip the parens if showdiff==yes
                if "(" in score_part:
                    score_part = score_part.split("(")[0].strip()

                try:
                    score_val = int(score_part)
                except:
                    continue

                name_obj = session.query(Name).filter_by(name=nm).first()
                if not name_obj:
                    name_obj = Name(name=nm)
                    session.add(name_obj)
                    session.commit()
                    session.refresh(name_obj)

                _, diff, did_update = self.update_score(session, name_obj, score_val, category.value)
                if did_update:
                    updated += 1
                else:
                    ignored += 1
            session.commit()
            await interaction.response.send_message(f"✅ Import complete. Updated: {updated}, Ignored: {ignored}", ephemeral=True)
        finally:
            session.close()


async def setup(bot):
    await bot.add_cog(ScoringCog(bot))

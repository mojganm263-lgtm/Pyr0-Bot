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
        if category == "kill":
            current = name_obj.kill_score
        else:
            current = name_obj.vs_score

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
                    await interaction.response.send_message(f"✅ {category.name} updated: {name} = +{diff:,} {emoji}", ephemeral=True)
                else:
                    await interaction.response.send_message(f"✅ {category.name} updated: {name} = {new_total:,} {emoji}", ephemeral=True)
            else:
                current = obj.kill_score if category.value == "kill" else obj.vs_score
                await interaction.response.send_message(f"⚠️ Ignored update: {name} already has a higher or equal score ({current:,}).", ephemeral=True)
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

            data = {}
            for n in names:
                val = n.kill_score if category.value == "kill" else n.vs_score
                data[n.name] = val
            sorted_data = dict(sorted(data.items(), key=lambda x: x[1] if x[1] is not None else 0, reverse=True))
            emoji = "🔥" if category.value == "kill" else "🛠"

            if mode.value == "table":
                table_lines = []
                for i, (nm, val) in enumerate(sorted_data.items(), start=1):
                    name_obj = session.query(Name).filter_by(name=nm).first()
                    prev_hist = session.query(ScoreHistory).filter_by(name_id=name_obj.id, category=category.value).order_by(ScoreHistory.timestamp.desc()).offset(1).first()
                    prev_val = prev_hist.value if prev_hist else 0
                    diff = val - prev_val
                    if showdiff and showdiff.value == "yes":
                        line = f"#{i} {nm} {diff:+,} {emoji}"
                    else:
                        line = f"#{i} {nm} {val:,} {emoji}"
                    table_lines.append(line)

                table_str = "\n".join(table_lines)
                embed = discord.Embed(title=f"{category.name} Table", description=f"```\n{table_str}\n```", color=0x00ffcc)
                await interaction.response.send_message(embed=embed)
            else:
                # Graph logic unchanged
                fig, ax = plt.subplots()
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
            # ---------- FILE: cogs/scoring.py (continued: removename) ----------
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

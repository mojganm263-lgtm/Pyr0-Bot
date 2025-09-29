# ---------- FILE: cogs/scoring.py ----------
import discord
from discord.ext import commands
from discord import app_commands
from database import SessionLocal, Name, ScoreHistory
from cogs.utilities import split_long_message
import matplotlib.pyplot as plt
from io import BytesIO
import matplotlib
matplotlib.use("Agg")

class ScoringCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # ---------- Admin Check ----------
    async def is_admin(self, interaction):
        return interaction.user.guild_permissions.administrator

    # ---------- Add/Update Score ----------
    @app_commands.command(name="addscore", description="Add or update a score for a name (Admin only)")
    @app_commands.describe(category="Choose score type", name="Name to track", value="Value to add/update")
    @app_commands.choices(category=[
        app_commands.Choice(name="Kill Score", value="kill"),
        app_commands.Choice(name="VS Score", value="vs")
    ])
    async def addscore(self, interaction, category: app_commands.Choice[str], name: str, value: int):
        if not await self.is_admin(interaction):
            await interaction.response.send_message("❌ Admins only.", ephemeral=True)
            return

        session = SessionLocal()
        try:
            name_obj = session.query(Name).filter_by(name=name).first()
            if not name_obj:
                name_obj = Name(name=name)
                session.add(name_obj)

            if category.value == "kill":
                name_obj.kill_score = value
            else:
                name_obj.vs_score = value

            history = ScoreHistory(name=name_obj, category=category.value, value=value)
            session.add(history)
            session.commit()

            await interaction.response.send_message(f"✅ {category.name} updated: {name} = {value:,}", ephemeral=True)
        finally:
            session.close()

    # ---------- List Names with Autocomplete ----------
    @app_commands.command(name="listnames", description="List all names in a score category")
    @app_commands.describe(category="Choose score type")
    @app_commands.choices(category=[
        app_commands.Choice(name="Kill Score", value="kill"),
        app_commands.Choice(name="VS Score", value="vs")
    ])
    async def listnames(self, interaction, category: app_commands.Choice[str]):
        session = SessionLocal()
        try:
            names = session.query(Name).all()
            if not names:
                await interaction.response.send_message(f"⚠️ No names in {category.name}.", ephemeral=True)
                return

            msg = f"📋 **Names in {category.name}:**\n"
            msg += "\n".join([n.name for n in names])
            await interaction.response.send_message(msg, ephemeral=True)
        finally:
            session.close()

    # ---------- Show Scores (Table or Graph) ----------
    @app_commands.command(name="showscores", description="Show scores as table or graph")
    @app_commands.describe(category="Choose score type", mode="Display as table or graph")
    @app_commands.choices(category=[
        app_commands.Choice(name="Kill Score", value="kill"),
        app_commands.Choice(name="VS Score", value="vs")
    ])
    @app_commands.choices(mode=[
        app_commands.Choice(name="Table", value="table"),
        app_commands.Choice(name="Graph", value="graph")
    ])
    async def showscores(self, interaction, category: app_commands.Choice[str], mode: app_commands.Choice[str]):
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

            if mode.value == "table":
                msg = f"📊 **{category.name} Table**\n"
                msg += "\n".join([f"- {name}: {val:,}" for name, val in data.items()])
                # Split long messages if needed
                for part in split_long_message(msg):
                    await interaction.response.send_message(part)
            else:
                fig, ax = plt.subplots()
                ax.bar(data.keys(), data.values(), color='skyblue')
                ax.set_ylabel("Score")
                ax.set_title(f"{category.name}")
                ax.get_yaxis().set_major_formatter(matplotlib.ticker.FuncFormatter(lambda x, p: format(int(x), ',')))
                buf = BytesIO()
                plt.savefig(buf, format="png")
                buf.seek(0)
                await interaction.response.send_message(file=discord.File(buf, filename="graph.png"))
        finally:
            session.close()

# ---------- FILE: cogs/scoring.py ----------
import discord
from discord.ext import commands
from discord import app_commands
from database import SessionLocal, Name, ScoreHistory
from cogs.utilities import split_long_message
import matplotlib.pyplot as plt
import matplotlib
import seaborn as sns
import pandas as pd
from io import BytesIO
from tabulate import tabulate

matplotlib.use("Agg")
sns.set_theme()

class ScoringCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

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
            obj = session.query(Name).filter_by(name=name).first()
            if not obj:
                obj = Name(name=name)
                session.add(obj)
            prev_val = obj.kill_score if category.value=="kill" else obj.vs_score
            if category.value=="kill":
                obj.kill_score = value
            else:
                obj.vs_score = value
            hist = ScoreHistory(name=obj, category=category.value, value=value)
            session.add(hist)
            session.commit()
            emoji = "🔥" if category.value=="kill" else "🛠"
            diff = value - prev_val if prev_val is not None else value
            await interaction.response.send_message(f"✅ {category.name} updated: {name} = {value:,} ({diff:+,}) {emoji}", ephemeral=True)
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
                val = n.kill_score if category.value=="kill" else n.vs_score
                data[n.name] = val
            sorted_data = dict(sorted(data.items(), key=lambda x: x[1], reverse=True))
            emoji = "🔥" if category.value=="kill" else "🛠"

            if mode.value=="table":
                table_rows = []
                prev_vals = {n.name:(session.query(ScoreHistory).filter_by(name_id=n.id, category=category.value).order_by(ScoreHistory.timestamp.desc()).offset(1).first().value if session.query(ScoreHistory).filter_by(name_id=n.id, category=category.value).count()>1 else n.kill_score if category.value=="kill" else n.vs_score) for n in names}
                for i, (name, val) in enumerate(sorted_data.items(), start=1):
                    diff = val - prev_vals.get(name, 0)
                    table_rows.append([f"#{i}", name, f"{val:,}", f"{diff:+,}", emoji])
                table_str = tabulate(table_rows, headers=["Rank", "Name", "Score", "Δ", ""])
                embed = discord.Embed(title=f"{category.name} Table", description=f"```{table_str}```", color=0x00ffcc)
                await interaction.response.send_message(embed=embed)
            else:
                fig, ax = plt.subplots()
                ax.bar(sorted_data.keys(), sorted_data.values(), color='skyblue')
                ax.set_ylabel("Score")
                ax.set_title(f"{category.name}")
                buf = BytesIO()
                plt.savefig(buf, format="png")
                buf.seek(0)
                await interaction.response.send_message(file=discord.File(buf, filename="graph.png"))
        finally:
            session.close()

    # ---------- Leaderboard ----------
    @app_commands.command(name="leaderboard", description="Show leaderboard for a category")
    @app_commands.describe(category="Choose score type", top="Optional top N")
    @app_commands.choices(category=[
        app_commands.Choice(name="Kill Score", value="kill"),
        app_commands.Choice(name="VS Score", value="vs")
    ])
    async def leaderboard(self, interaction, category: app_commands.Choice[str], top: int = None):
        session = SessionLocal()
        try:
            names = session.query(Name).all()
            if not names:
                await interaction.response.send_message("⚠️ No scores available.", ephemeral=True)
                return
            data = {}
            for n in names:
                val = n.kill_score if category.value=="kill" else n.vs_score
                data[n.name] = val
            sorted_data = sorted(data.items(), key=lambda x: x[1], reverse=True)
            if top:
                sorted_data = sorted_data[:top]
            emoji = "🔥" if category.value=="kill" else "🛠"
            embed = discord.Embed(title=f"{category.name} Leaderboard", color=0xffa500)
            for i, (name, val) in enumerate(sorted_data, start=1):
                embed.add_field(name=f"#{i} {name}", value=f"{val:,} {emoji}", inline=False)
            await interaction.response.send_message(embed=embed)
        finally:
            session.close()

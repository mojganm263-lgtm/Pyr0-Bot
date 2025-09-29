import discord
from discord import app_commands, Interaction
from discord.ext import commands
from sqlalchemy.orm import Session
from datetime import datetime
import pandas as pd
import io
import os
import seaborn as sns
import matplotlib.pyplot as plt
from tabulate import tabulate

from models import Score, History, Channel
import utils

def setup(bot: commands.Bot, SessionLocal):
    tree = bot.tree
    setup_channels(tree)
    setup_scores(tree)
    setup_import_export(tree)
    setup_leaderboards(tree)
    setup_history(tree)

# ---------------- Channel ----------------
def setup_channels(tree):

    @tree.command(name="registerchannel", description="Register this channel for score tracking")
    async def register_channel(interaction: Interaction):
        session = utils.get_session()
        try:
            guild_id, channel_id = str(interaction.guild_id), str(interaction.channel_id)
            existing = session.query(Channel).filter_by(guild_id=guild_id, channel_id=channel_id).first()
            if existing:
                await interaction.response.send_message("This channel is already registered.")
                return
            session.add(Channel(guild_id=guild_id, channel_id=channel_id))
            session.commit()
            await interaction.response.send_message("Channel registered successfully.")
        finally:
            session.close()

    @tree.command(name="unregisterchannel", description="Unregister this channel from score tracking")
    async def unregister_channel(interaction: Interaction):
        session = utils.get_session()
        try:
            guild_id, channel_id = str(interaction.guild_id), str(interaction.channel_id)
            channel = session.query(Channel).filter_by(guild_id=guild_id, channel_id=channel_id).first()
            if not channel:
                await interaction.response.send_message("This channel is not registered.")
                return
            session.delete(channel)
            session.commit()
            await interaction.response.send_message("Channel unregistered successfully.")
        finally:
            session.close()

# ---------------- Scores ----------------
def setup_scores(tree):

    @tree.command(name="addscore", description="Add or update a score")
    @app_commands.describe(name="Player name", category="Category", value="Score value")
    async def add_score(interaction: Interaction, name: str, category: str, value: float):
        session = utils.get_session()
        try:
            existing = session.query(Score).filter_by(name=name, category=category).first()
            if existing:
                history = History(score=existing, old_value=existing.value, new_value=value)
                existing.value = value
                existing.timestamp = datetime.utcnow()
                session.add(history)
                msg = f"Updated score for {name} in {category} to {value}"
            else:
                session.add(Score(name=name, category=category, value=value))
                msg = f"Added score for {name} in {category}: {value}"
            session.commit()
            await interaction.response.send_message(msg)
        finally:
            session.close()

    @tree.command(name="showscore", description="Show score for a player")
    @app_commands.describe(name="Player name", category="Category")
    @app_commands.autocomplete(name=utils.name_autocomplete)
    async def show_score(interaction: Interaction, name: str, category: str):
        session = utils.get_session()
        try:
            score = session.query(Score).filter_by(name=name, category=category).first()
            if score:
                await interaction.response.send_message(f"{name} in {category}: {score.value} (last updated {score.timestamp})")
            else:
                await interaction.response.send_message(f"No score found for {name} in {category}")
        finally:
            session.close()

    @tree.command(name="clearscore", description="Remove a player's score")
    @app_commands.describe(name="Player name", category="Category")
    @app_commands.autocomplete(name=utils.name_autocomplete)
    async def clear_score(interaction: Interaction, name: str, category: str):
        session = utils.get_session()
        try:
            deleted = session.query(Score).filter_by(name=name, category=category).delete()
            session.commit()
            msg = f"Score for {name} in {category} removed." if deleted else f"No score found for {name} in {category}."
            await interaction.response.send_message(msg)
        finally:
            session.close()

# ---------------- Import/Export ----------------
def setup_import_export(tree):
    @tree.command(name="exportdata", description="Export scores to a file")
    async def export_data(interaction: Interaction, filetype: str = "csv"):
        session = utils.get_session()
        try:
            scores = session.query(Score).all()
            if not scores:
                await interaction.response.send_message("No data to export.")
                return
            df = pd.DataFrame([{"name": s.name, "category": s.category, "value": s.value, "timestamp": s.timestamp} for s in scores])
            buffer = io.BytesIO()
            filename = f"scores.{filetype.lower()}"
            if filetype.lower() == "csv":
                df.to_csv(buffer, index=False)
            elif filetype.lower() in ["xlsx", "excel"]:
                df.to_excel(buffer, index=False, engine="openpyxl")
            elif filetype.lower() == "json":
                df.to_json(buffer, orient="records", lines=True)
            else:
                await interaction.response.send_message("Unsupported file type.")
                return
            buffer.seek(0)
            await interaction.response.send_message(f"Here is the exported data ({filename}):", file=discord.File(buffer, filename))
        finally:
            session.close()

# ---------------- Leaderboards & History ----------------
# ... (similar to above, fully implemented as in your previous bot)
# ---------------- Leaderboards ----------------
def setup_leaderboards(tree):

    @tree.command(name="leaderboard", description="Show leaderboard in text")
    async def leaderboard(interaction: Interaction, category: str = None, top: int = 10):
        session = utils.get_session()
        try:
            query = session.query(Score)
            if category:
                query = query.filter(Score.category == category)
            scores = query.order_by(Score.value.desc()).limit(top).all()
            if not scores:
                await interaction.response.send_message("No scores found.")
                return
            table_data = [(i+1, s.name, s.category, s.value) for i, s in enumerate(scores)]
            table = tabulate(table_data, headers=["Rank", "Name", "Category", "Score"], tablefmt="github")
            await interaction.response.send_message(f"```\n{table}\n```")
        finally:
            session.close()

    @tree.command(name="leaderboardchart", description="Show leaderboard as a chart")
    async def leaderboard_chart(interaction: Interaction, category: str = None, top: int = 10):
        session = utils.get_session()
        try:
            query = session.query(Score)
            if category:
                query = query.filter(Score.category == category)
            scores = query.order_by(Score.value.desc()).limit(top).all()
            if not scores:
                await interaction.response.send_message("No scores found.")
                return
            names = [s.name for s in scores]
            values = [s.value for s in scores]
            plt.figure(figsize=(8, 6))
            sns.barplot(x=values, y=names, palette="viridis")
            plt.title(f"Leaderboard ({category if category else 'All'})")
            plt.xlabel("Score")
            plt.ylabel("Name")
            file_path = "/tmp/leaderboard.png"
            plt.tight_layout()
            plt.savefig(file_path)
            plt.close()
            await interaction.response.send_message("Leaderboard chart:", file=discord.File(file_path))
        finally:
            session.close()
            if os.path.exists(file_path):
                os.remove(file_path)

# ---------------- History ----------------
def setup_history(tree):

    @tree.command(name="history", description="Show score history for a name")
    async def history(interaction: Interaction, name: str):
        session = utils.get_session()
        try:
            scores = session.query(Score).filter(Score.name == name).all()
            if not scores:
                await interaction.response.send_message(f"No scores for {name}.")
                return
            history_data = []
            for score in scores:
                for h in score.history:
                    history_data.append((score.category, h.old_value, h.new_value, h.timestamp))
            if not history_data:
                await interaction.response.send_message(f"No history for {name}.")
                return
            history_data.sort(key=lambda x: x[3])
            table = tabulate(
                [(cat, old, new, ts.strftime("%Y-%m-%d %H:%M")) for cat, old, new, ts in history_data],
                headers=["Category", "Old", "New", "Timestamp"], tablefmt="github"
            )
            await interaction.response.send_message(f"History for {name}:\n```\n{table}\n```")
        finally:
            session.close()

    @tree.command(name="diff", description="Compare score changes for a name")
    async def diff(interaction: Interaction, name: str, category: str):
        session = utils.get_session()
        try:
            score = session.query(Score).filter_by(name=name, category=category).first()
            if not score or not score.history:
                await interaction.response.send_message(f"No history for {name} in {category}.")
                return
            prev = score.history[0].old_value
            differences = [utils.diff_values(prev, h.new_value) for h in score.history]
            await interaction.response.send_message(f"Score differences for {name} in {category}:\n" + "\n".join(differences))
        finally:
            session.close()

# ---------------- Import ----------------
def setup_import_export(tree):

    @tree.command(name="importdata", description="Import scores from a file")
    async def import_data(interaction: Interaction, attachment: discord.Attachment):
        session = utils.get_session()
        try:
            if not attachment.filename.endswith((".csv", ".xlsx", ".json")):
                await interaction.response.send_message("File must be CSV, XLSX, or JSON.")
                return
            file_bytes = await attachment.read()
            buffer = io.BytesIO(file_bytes)
            if attachment.filename.endswith(".csv"):
                df = pd.read_csv(buffer)
            elif attachment.filename.endswith(".xlsx"):
                df = pd.read_excel(buffer, engine="openpyxl")
            elif attachment.filename.endswith(".json"):
                df = pd.read_json(buffer, lines=True)
            count = 0
            for _, row in df.iterrows():
                score = Score(
                    name=row["name"],
                    category=row["category"],
                    value=row["value"],
                    timestamp=pd.to_datetime(row["timestamp"]) if "timestamp" in row else datetime.utcnow()
                )
                session.add(score)
                count += 1
            session.commit()
            await interaction.response.send_message(f"Imported {count} scores successfully.")
        finally:
            session.close()

# ---------------- Translator ----------------
def setup_translator(tree):

    @tree.command(name="translate", description="Translate text to a target language")
    async def translate(interaction: Interaction, text: str, target_lang: str = "en"):
        translated = utils.translate_text(text, target_lang)
        await interaction.response.send_message(f"Translated ({target_lang}): {translated}")

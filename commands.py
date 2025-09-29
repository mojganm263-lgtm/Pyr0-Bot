# ---------- commands.py — PART 5A: channel + scoring commands ----------
import discord
from discord import app_commands, Interaction
from discord.ext import commands
from sqlalchemy.orm import Session
from datetime import datetime

from models import Score, History, Channel
import utils

def setup(bot: commands.Bot, SessionLocal):
    tree = bot.tree

    # -------- Channel Commands --------
    @tree.command(name="setchannel", description="Register this channel for score tracking")
    async def set_channel(interaction: Interaction):
        session: Session = utils.get_session()
        try:
            guild_id = str(interaction.guild.id)
            channel_id = str(interaction.channel.id)

            # Replace existing or add new
            existing = session.query(Channel).filter_by(guild_id=guild_id).first()
            if existing:
                existing.channel_id = channel_id
            else:
                new_ch = Channel(guild_id=guild_id, channel_id=channel_id)
                session.add(new_ch)

            session.commit()
            await interaction.response.send_message(f"Channel <#{channel_id}> registered for this guild.")
        except Exception as e:
            session.rollback()
            await interaction.response.send_message(f"Error setting channel: {e}")
        finally:
            session.close()

    @tree.command(name="clearchannel", description="Unregister score channel for this guild")
    async def clear_channel(interaction: Interaction):
        session: Session = utils.get_session()
        try:
            guild_id = str(interaction.guild.id)
            deleted = session.query(Channel).filter_by(guild_id=guild_id).delete()
            session.commit()
            if deleted:
                await interaction.response.send_message("Channel unregistered.")
            else:
                await interaction.response.send_message("No channel was registered.")
        except Exception as e:
            session.rollback()
            await interaction.response.send_message(f"Error clearing channel: {e}")
        finally:
            session.close()

    # -------- Scoring Commands --------
    @tree.command(name="addscore", description="Add or update a score for a player")
    @app_commands.describe(name="Player name", category="Category", value="Score value")
    async def add_score(interaction: Interaction, name: str, category: str, value: float):
        session: Session = utils.get_session()
        try:
            existing = session.query(Score).filter_by(name=name, category=category).first()
            if existing:
                # Update with history
                history = History(score=existing, old_value=existing.value, new_value=value)
                existing.value = value
                existing.timestamp = datetime.utcnow()
                session.add(history)
                msg = f"Updated score for {name} in {category} to {value}"
            else:
                new_score = Score(name=name, category=category, value=value)
                session.add(new_score)
                msg = f"Added score for {name} in {category}: {value}"

            session.commit()
            await interaction.response.send_message(msg)
        except Exception as e:
            session.rollback()
            await interaction.response.send_message(f"Error adding score: {e}")
        finally:
            session.close()

    @tree.command(name="showscore", description="Show score for a player in a category")
    @app_commands.describe(name="Player name", category="Category")
    @app_commands.autocomplete(name=utils.name_autocomplete)
    async def show_score(interaction: Interaction, name: str, category: str):
        session: Session = utils.get_session()
        try:
            score = session.query(Score).filter_by(name=name, category=category).first()
            if score:
                await interaction.response.send_message(
                    f"{name} in {category}: {score.value} (last updated {score.timestamp})"
                )
            else:
                await interaction.response.send_message(f"No score found for {name} in {category}")
        except Exception as e:
            await interaction.response.send_message(f"Error showing score: {e}")
        finally:
            session.close()

    @tree.command(name="clearscore", description="Remove a player's score in a category")
    @app_commands.describe(name="Player name", category="Category")
    @app_commands.autocomplete(name=utils.name_autocomplete)
    async def clear_score(interaction: Interaction, name: str, category: str):
        session: Session = utils.get_session()
        try:
            deleted = session.query(Score).filter_by(name=name, category=category).delete()
            session.commit()
            if deleted:
                await interaction.response.send_message(f"Score for {name} in {category} removed.")
            else:
                await interaction.response.send_message(f"No score found for {name} in {category}.")
        except Exception as e:
            session.rollback()
            await interaction.response.send_message(f"Error clearing score: {e}")
        finally:
            session.close()
          # ---------- commands.py — PART 5B: import/export ----------
import pandas as pd
import os

def setup_import_export(tree, SessionLocal):

    @tree.command(name="importcsv", description="Import scores from a CSV file")
    async def import_csv(interaction: Interaction, attachment: discord.Attachment):
        session: Session = utils.get_session()
        try:
            if not attachment.filename.endswith(".csv"):
                await interaction.response.send_message("Please upload a CSV file.")
                return

            file_path = f"/tmp/{attachment.filename}"
            await attachment.save(file_path)
            df = pd.read_csv(file_path)

            # Expecting: name, category, value
            for _, row in df.iterrows():
                name, category, value = row["name"], row["category"], float(row["value"])
                existing = session.query(Score).filter_by(name=name, category=category).first()
                if existing:
                    history = History(score=existing, old_value=existing.value, new_value=value)
                    existing.value = value
                    existing.timestamp = datetime.utcnow()
                    session.add(history)
                else:
                    new_score = Score(name=name, category=category, value=value)
                    session.add(new_score)

            session.commit()
            await interaction.response.send_message("CSV imported successfully.")
        except Exception as e:
            session.rollback()
            await interaction.response.send_message(f"Error importing CSV: {e}")
        finally:
            session.close()
            if os.path.exists(file_path):
                os.remove(file_path)

    @tree.command(name="importexcel", description="Import scores from an Excel file")
    async def import_excel(interaction: Interaction, attachment: discord.Attachment):
        session: Session = utils.get_session()
        try:
            if not (attachment.filename.endswith(".xlsx") or attachment.filename.endswith(".xls")):
                await interaction.response.send_message("Please upload an Excel file (.xlsx or .xls).")
                return

            file_path = f"/tmp/{attachment.filename}"
            await attachment.save(file_path)
            df = pd.read_excel(file_path)

            for _, row in df.iterrows():
                name, category, value = row["name"], row["category"], float(row["value"])
                existing = session.query(Score).filter_by(name=name, category=category).first()
                if existing:
                    history = History(score=existing, old_value=existing.value, new_value=value)
                    existing.value = value
                    existing.timestamp = datetime.utcnow()
                    session.add(history)
                else:
                    new_score = Score(name=name, category=category, value=value)
                    session.add(new_score)

            session.commit()
            await interaction.response.send_message("Excel imported successfully.")
        except Exception as e:
            session.rollback()
            await interaction.response.send_message(f"Error importing Excel: {e}")
        finally:
            session.close()
            if os.path.exists(file_path):
                os.remove(file_path)

    @tree.command(name="exportcsv", description="Export all scores to a CSV file")
    async def export_csv(interaction: Interaction):
        session: Session = utils.get_session()
        try:
            scores = session.query(Score).all()
            if not scores:
                await interaction.response.send_message("No scores to export.")
                return

            data = [{"name": s.name, "category": s.category, "value": s.value, "timestamp": s.timestamp} for s in scores]
            df = pd.DataFrame(data)

            file_path = "/tmp/scores.csv"
            df.to_csv(file_path, index=False)

            await interaction.response.send_message("Here is the exported CSV:", file=discord.File(file_path))
        except Exception as e:
            await interaction.response.send_message(f"Error exporting CSV: {e}")
        finally:
            session.close()
            if os.path.exists(file_path):
                os.remove(file_path)

    @tree.command(name="exportexcel", description="Export all scores to an Excel file")
    async def export_excel(interaction: Interaction):
        session: Session = utils.get_session()
        try:
            scores = session.query(Score).all()
            if not scores:
                await interaction.response.send_message("No scores to export.")
                return

            data = [{"name": s.name, "category": s.category, "value": s.value, "timestamp": s.timestamp} for s in scores]
            df = pd.DataFrame(data)

            file_path = "/tmp/scores.xlsx"
            df.to_excel(file_path, index=False)

            await interaction.response.send_message("Here is the exported Excel file:", file=discord.File(file_path))
        except Exception as e:
            await interaction.response.send_message(f"Error exporting Excel: {e}")
        finally:
            session.close()
            if os.path.exists(file_path):
                os.remove(file_path)
              # ---------- commands.py — PART 5C: leaderboards ----------
import seaborn as sns
import matplotlib.pyplot as plt

def setup_leaderboards(tree, SessionLocal):

    @tree.command(name="leaderboard", description="Show the leaderboard (text format)")
    async def leaderboard(interaction: Interaction, category: str = None, top: int = 10):
        session: Session = utils.get_session()
        try:
            query = session.query(Score)
            if category:
                query = query.filter(Score.category == category)
            scores = query.order_by(Score.value.desc()).limit(top).all()

            if not scores:
                await interaction.response.send_message("No scores found for this leaderboard.")
                return

            table_data = [(i+1, s.name, s.category, s.value) for i, s in enumerate(scores)]
            table = tabulate(table_data, headers=["Rank", "Name", "Category", "Score"], tablefmt="github")

            await interaction.response.send_message(f"```\n{table}\n```")
        except Exception as e:
            await interaction.response.send_message(f"Error showing leaderboard: {e}")
        finally:
            session.close()

    @tree.command(name="leaderboardchart", description="Show the leaderboard as a chart")
    async def leaderboard_chart(interaction: Interaction, category: str = None, top: int = 10):
        session: Session = utils.get_session()
        try:
            query = session.query(Score)
            if category:
                query = query.filter(Score.category == category)
            scores = query.order_by(Score.value.desc()).limit(top).all()

            if not scores:
                await interaction.response.send_message("No scores found for this leaderboard.")
                return

            names = [s.name for s in scores]
            values = [s.value for s in scores]

            plt.figure(figsize=(8, 6))
            sns.barplot(x=values, y=names, palette="viridis")
            plt.title(f"Leaderboard ({category if category else 'All Categories'})")
            plt.xlabel("Score")
            plt.ylabel("Name")

            file_path = "/tmp/leaderboard.png"
            plt.tight_layout()
            plt.savefig(file_path)
            plt.close()

            await interaction.response.send_message("Here’s the leaderboard chart:", file=discord.File(file_path))
        except Exception as e:
            await interaction.response.send_message(f"Error generating chart: {e}")
        finally:
            session.close()
            if os.path.exists(file_path):
                os.remove(file_path)
              # ---------- commands.py — PART 5D: history & diff ----------
def setup_history(tree, SessionLocal):

    @tree.command(name="history", description="Show the score history for a name")
    async def history(interaction: Interaction, name: str):
        session: Session = utils.get_session()
        try:
            scores = session.query(Score).filter(Score.name == name).all()
            if not scores:
                await interaction.response.send_message(f"No scores found for {name}.")
                return

            history_data = []
            for score in scores:
                for h in score.history:
                    history_data.append((score.category, h.old_value, h.new_value, h.timestamp))

            if not history_data:
                await interaction.response.send_message(f"No history recorded for {name}.")
                return

            history_data.sort(key=lambda x: x[3])  # sort by timestamp
            table = tabulate(
                [(cat, old, new, ts.strftime("%Y-%m-%d %H:%M")) for cat, old, new, ts in history_data],
                headers=["Category", "Old", "New", "Timestamp"],
                tablefmt="github"
            )

            await interaction.response.send_message(f"History for {name}:\n```\n{table}\n```")
        except Exception as e:
            await interaction.response.send_message(f"Error showing history: {e}")
        finally:
            session.close()

    @tree.command(name="diff", description="Compare two score values for a name")
    async def diff(interaction: Interaction, name: str, category: str):
        session: Session = utils.get_session()
        try:
            score = session.query(Score).filter(Score.name == name, Score.category == category).first()
            if not score:
                await interaction.response.send_message(f"No score found for {name} in category {category}.")
                return

            if not score.history:
                await interaction.response.send_message(f"No history available for {name} in category {category}.")
                return

            # Use utils.diff_values to show changes
            differences = []
            prev = score.history[0].old_value
            for h in score.history:
                differences.append(utils.diff_values(prev, h.new_value))
                prev = h.new_value

            diffs = "\n".join(differences)
            await interaction.response.send_message(f"Score differences for {name} in {category}:\n{diffs}")
        except Exception as e:
            await interaction.response.send_message(f"Error calculating diff: {e}")
        finally:
            session.close()
          # ---------- commands.py — PART 5E: channel registration ----------
def setup_channels(tree, SessionLocal):

    @tree.command(name="registerchannel", description="Register this channel for score tracking")
    async def register_channel(interaction: Interaction):
        session: Session = utils.get_session()
        try:
            guild_id = str(interaction.guild_id)
            channel_id = str(interaction.channel_id)

            existing = session.query(Channel).filter(
                Channel.guild_id == guild_id,
                Channel.channel_id == channel_id
            ).first()

            if existing:
                await interaction.response.send_message("This channel is already registered.")
                return

            channel = Channel(guild_id=guild_id, channel_id=channel_id)
            session.add(channel)
            session.commit()
            await interaction.response.send_message("Channel registered successfully.")
        except Exception as e:
            await interaction.response.send_message(f"Error registering channel: {e}")
        finally:
            session.close()

    @tree.command(name="unregisterchannel", description="Unregister this channel from score tracking")
    async def unregister_channel(interaction: Interaction):
        session: Session = utils.get_session()
        try:
            guild_id = str(interaction.guild_id)
            channel_id = str(interaction.channel_id)

            channel = session.query(Channel).filter(
                Channel.guild_id == guild_id,
                Channel.channel_id == channel_id
            ).first()

            if not channel:
                await interaction.response.send_message("This channel is not registered.")
                return

            session.delete(channel)
            session.commit()
            await interaction.response.send_message("Channel unregistered successfully.")
        except Exception as e:
            await interaction.response.send_message(f"Error unregistering channel: {e}")
        finally:
            session.close()
          # ---------- commands.py — PART 5F: import & export ----------
import io
import pandas as pd

def setup_import_export(tree, SessionLocal):

    @tree.command(name="exportdata", description="Export scores to a file")
    async def export_data(interaction: Interaction, filetype: str = "csv"):
        session: Session = utils.get_session()
        try:
            scores = session.query(Score).all()
            if not scores:
                await interaction.response.send_message("No data to export.")
                return

            data = [{
                "name": s.name,
                "category": s.category,
                "value": s.value,
                "timestamp": s.timestamp
            } for s in scores]

            df = pd.DataFrame(data)

            buffer = io.BytesIO()
            filename = f"scores.{filetype.lower()}"

            if filetype.lower() == "csv":
                df.to_csv(buffer, index=False)
            elif filetype.lower() in ["xlsx", "excel"]:
                df.to_excel(buffer, index=False, engine="openpyxl")
            elif filetype.lower() == "json":
                df.to_json(buffer, orient="records", lines=True)
            else:
                await interaction.response.send_message("Unsupported file type. Use csv, xlsx, or json.")
                return

            buffer.seek(0)
            await interaction.response.send_message(
                f"Here is the exported data ({filename}):",
                file=discord.File(buffer, filename)
            )
        except Exception as e:
            await interaction.response.send_message(f"Error exporting data: {e}")
        finally:
            session.close()

    @tree.command(name="importdata", description="Import scores from a file")
    async def import_data(interaction: Interaction, attachment: discord.Attachment):
        session: Session = utils.get_session()
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
            else:
                await interaction.response.send_message("Unsupported file type.")
                return

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
        except Exception as e:
            await interaction.response.send_message(f"Error importing data: {e}")
        finally:
            session.close()
          # ---------- utils.py — PART 5G: error handling & helpers ----------
from sqlalchemy.orm import sessionmaker
from database import engine, SessionLocal    # engine and session factory
from models import Score                       # import your DB model from models.py
from datetime import datetime

SessionLocal = sessionmaker(bind=engine)

# ---------- Database session helper ----------
def get_session():
    return SessionLocal()

# ---------- Diff calculation helper ----------
def diff_values(old: int, new: int) -> str:
    diff = new - old
    sign = "+" if diff >= 0 else "-"
    return f"{old} → {new} ({sign}{abs(diff)})"

# ---------- Safe score retrieval ----------
def get_score(session, name: str, category: str):
    return session.query(Score).filter(Score.name == name, Score.category == category).first()

# ---------- Chunked message helper ----------
async def send_long_message(interaction, header: str, lines: list[str], ephemeral=False):
    max_chars = 1800
    chunk = []
    current_len = len(header) + 2
    for line in lines:
        if current_len + len(line) + 1 > max_chars and chunk:
            msg = header + "\n" + "\n".join(chunk)
            if not hasattr(interaction, "followup_sent") or not interaction.followup_sent:
                await interaction.response.send_message(msg, ephemeral=ephemeral)
                interaction.followup_sent = True
            else:
                await interaction.followup.send(msg, ephemeral=ephemeral)
            chunk = []
            current_len = len(header) + 2
        chunk.append(line)
        current_len += len(line) + 1

    if chunk:
        msg = header + "\n" + "\n".join(chunk)
        if not hasattr(interaction, "followup_sent") or not interaction.followup_sent:
            await interaction.response.send_message(msg, ephemeral=ephemeral)
            interaction.followup_sent = True
        else:
            await interaction.followup.send(msg, ephemeral=ephemeral)

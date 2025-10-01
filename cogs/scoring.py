# ---------- FILE: cogs/scoring.py ----------
import discord
from discord.ext import commands
from discord import app_commands
from database import SessionLocal, Name, ScoreHistory
from cogs.utilities import split_long_message
import datetime


class Scoring(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # ---------- Helper: apply score rule ----------
    def apply_score_rule(self, existing_score, new_score):
        if existing_score is None:
            return new_score, new_score, True  # permanent first score
        if new_score > existing_score:
            diff = new_score - existing_score
            return existing_score + diff, diff, True
        return existing_score, 0, False  # ignore subtraction

    # ---------- addscore ----------
    @app_commands.command(name="addscore", description="Add a score to a name")
    @app_commands.describe(name="The person's name", score="Score value (integer)", showdiff="yes or no (default no)")
    async def addscore(self, interaction: discord.Interaction, name: str, score: int, showdiff: str = "no"):
        session = SessionLocal()
        try:
            db_name = session.query(Name).filter_by(name=name).first()
            if not db_name:
                db_name = Name(name=name, score=0)
                session.add(db_name)
                session.commit()

            old_score = db_name.score
            new_total, diff, updated = self.apply_score_rule(old_score if old_score != 0 else None, score)

            if updated:
                db_name.score = new_total
                history = ScoreHistory(name_id=db_name.id, score=new_total, timestamp=datetime.datetime.utcnow())
                session.add(history)
                session.commit()

            msg = f"{name} now has {db_name.score} points."
            if showdiff.lower() == "yes" and updated and diff > 0:
                msg += f" (Δ+{diff})"
            await interaction.response.send_message(msg)

        finally:
            session.close()

    # ---------- showscores ----------
    @app_commands.command(name="showscores", description="Show all scores")
    @app_commands.describe(showdiff="yes or no (default no)")
    async def showscores(self, interaction: discord.Interaction, showdiff: str = "no"):
        session = SessionLocal()
        try:
            names = session.query(Name).all()
            if not names:
                await interaction.response.send_message("No scores found.")
                return

            lines = []
            for name in names:
                line = f"{name.name}: {name.score}"
                if showdiff.lower() == "yes":
                    history = (
                        session.query(ScoreHistory)
                        .filter_by(name_id=name.id)
                        .order_by(ScoreHistory.timestamp.desc())
                        .limit(2)
                        .all()
                    )
                    if len(history) == 2:
                        diff = history[0].score - history[1].score
                        if diff > 0:
                            line += f" (Δ+{diff})"
                lines.append(line)

            await split_long_message(interaction, "\n".join(lines))
        finally:
            session.close()

    # ---------- leaderboard ----------
    @app_commands.command(name="leaderboard", description="Show leaderboard")
    @app_commands.describe(showdiff="yes or no (default no)")
    async def leaderboard(self, interaction: discord.Interaction, showdiff: str = "no"):
        session = SessionLocal()
        try:
            names = session.query(Name).order_by(Name.score.desc()).all()
            if not names:
                await interaction.response.send_message("No scores found.")
                return

            embed = discord.Embed(title="Leaderboard", color=discord.Color.gold())
            for i, name in enumerate(names, start=1):
                line = f"{name.score}"
                if showdiff.lower() == "yes":
                    history = (
                        session.query(ScoreHistory)
                        .filter_by(name_id=name.id)
                        .order_by(ScoreHistory.timestamp.desc())
                        .limit(2)
                        .all()
                    )
                    if len(history) == 2:
                        diff = history[0].score - history[1].score
                        if diff > 0:
                            line += f" (Δ+{diff})"
                embed.add_field(name=f"{i}. {name.name}", value=line, inline=False)

            await interaction.response.send_message(embed=embed)
        finally:
            session.close()

    # ---------- export ----------
    @app_commands.command(name="export", description="Export scores")
    @app_commands.describe(showdiff="yes or no (default no)")
    async def export(self, interaction: discord.Interaction, showdiff: str = "no"):
        session = SessionLocal()
        try:
            names = session.query(Name).all()
            if not names:
                await interaction.response.send_message("No scores found.")
                return

            lines = []
            for name in names:
                line = f"{name.name}:{name.score}"
                if showdiff.lower() == "yes":
                    history = (
                        session.query(ScoreHistory)
                        .filter_by(name_id=name.id)
                        .order_by(ScoreHistory.timestamp.desc())
                        .limit(2)
                        .all()
                    )
                    if len(history) == 2:
                        diff = history[0].score - history[1].score
                        if diff > 0:
                            line += f" (Δ+{diff})"
                lines.append(line)

            await split_long_message(interaction, "\n".join(lines))
        finally:
            session.close()

    # ---------- import ----------
    @app_commands.command(name="import", description="Import scores")
    @app_commands.describe(data="Paste exported scores", showdiff="yes or no (default no)")
    async def import_scores(self, interaction: discord.Interaction, data: str, showdiff: str = "no"):
        session = SessionLocal()
        try:
            lines = data.splitlines()
            for line in lines:
                if ":" not in line:
                    continue
                parts = line.split(":")
                name = parts[0].strip()
                score_part = parts[1].strip()

                # Strip optional diff marker if present
                if "(" in score_part and showdiff.lower() == "yes":
                    score_part = score_part.split("(")[0].strip()

                score_val = int(score_part)

                db_name = session.query(Name).filter_by(name=name).first()
                if not db_name:
                    db_name = Name(name=name, score=0)
                    session.add(db_name)
                    session.commit()

                old_score = db_name.score
                new_total, diff, updated = self.apply_score_rule(old_score if old_score != 0 else None, score_val)
                if updated:
                    db_name.score = new_total
                    history = ScoreHistory(name_id=db_name.id, score=new_total, timestamp=datetime.datetime.utcnow())
                    session.add(history)
                    session.commit()

            await interaction.response.send_message("Import complete.")
        finally:
            session.close()


async def setup(bot):
    await bot.add_cog(Scoring(bot))

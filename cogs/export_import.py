# ---------- FILE: cogs/export_import.py ----------
import discord
from discord.ext import commands
from discord import app_commands
from database import SessionLocal, Name, ScoreHistory
import csv
import pandas as pd
from io import BytesIO
from cogs.utilities import split_long_message


class ExportImportCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # ---------- Export CSV ----------
    @app_commands.command(name="exportcsv", description="Export scores to CSV")
    @app_commands.describe(category="Choose score type to export", showdiff="Include diff column?")
    @app_commands.choices(category=[
        app_commands.Choice(name="Kill Score", value="kill"),
        app_commands.Choice(name="VS Score", value="vs")
    ])
    @app_commands.choices(showdiff=[
        app_commands.Choice(name="Yes", value="yes"),
        app_commands.Choice(name="No", value="no")
    ])
    async def exportcsv(self, interaction, category: app_commands.Choice[str], showdiff: app_commands.Choice[str] = None):
        session = SessionLocal()
        try:
            names = session.query(Name).all()
            if not names:
                await interaction.response.send_message("⚠️ No data to export.", ephemeral=True)
                return

            output = BytesIO()
            writer = csv.writer(output)
            if showdiff and showdiff.value == "yes":
                writer.writerow(["Name", "Score", "Δ"])
            else:
                writer.writerow(["Name", "Score"])

            for n in names:
                val = n.kill_score if category.value == "kill" else n.vs_score
                if showdiff and showdiff.value == "yes":
                    latest = session.query(ScoreHistory).filter_by(name_id=n.id, category=category.value).order_by(ScoreHistory.timestamp.desc()).first()
                    prev = session.query(ScoreHistory).filter_by(name_id=n.id, category=category.value).order_by(ScoreHistory.timestamp.desc()).offset(1).first()
                    if latest and prev:
                        diff = latest.value - prev.value
                    else:
                        diff = latest.value if latest else 0
                    writer.writerow([n.name, f"{val:,}", f"{diff:,}"])
                else:
                    writer.writerow([n.name, f"{val:,}"])

            output.seek(0)
            await interaction.response.send_message(file=discord.File(output, filename=f"{category.value}_scores.csv"))
        finally:
            session.close()

    # ---------- Import CSV ----------
    @app_commands.command(name="importcsv", description="Import scores from a CSV file (Admin only)")
    @app_commands.describe(category="kill or vs", showdiff="Expect diff column?")
    @app_commands.choices(showdiff=[
        app_commands.Choice(name="Yes", value="yes"),
        app_commands.Choice(name="No", value="no")
    ])
    async def importcsv(self, interaction, category: str, attachment: discord.Attachment, showdiff: app_commands.Choice[str] = None):
        session = SessionLocal()
        try:
            file_bytes = await attachment.read()
            lines = file_bytes.decode("utf-8").splitlines()
            reader = csv.reader(lines)
            headers = next(reader, None)
            updated, ignored = 0, 0

            for row in reader:
                if len(row) < 2:
                    continue
                name = row[0].strip()
                score_cell = row[1].strip()

                # If showdiff and score has "(Δ...)", strip it
                if "(" in score_cell:
                    score_cell = score_cell.split("(")[0].strip()

                try:
                    val = int(score_cell.replace(',', ''))
                except:
                    continue

                name_obj = session.query(Name).filter_by(name=name).first()
                if not name_obj:
                    name_obj = Name(name=name)
                    if category.lower() == "kill":
                        name_obj.kill_score = val
                    else:
                        name_obj.vs_score = val
                    session.add(name_obj)
                    updated += 1
                else:
                    prev_val = name_obj.kill_score if category.lower() == "kill" else name_obj.vs_score
                    if val > prev_val:
                        if category.lower() == "kill":
                            name_obj.kill_score = val
                        else:
                            name_obj.vs_score = val
                        updated += 1
                    else:
                        ignored += 1

            session.commit()
            await interaction.response.send_message(f"✅ Imported into {category}. Updated: {updated}, Ignored: {ignored}", ephemeral=True)
        finally:
            session.close()

    # ---------- Export Excel ----------
    @app_commands.command(name="exportexcel", description="Export scores to Excel")
    @app_commands.describe(category="Choose score type to export", showdiff="Include diff column?")
    @app_commands.choices(category=[
        app_commands.Choice(name="Kill Score", value="kill"),
        app_commands.Choice(name="VS Score", value="vs")
    ])
    @app_commands.choices(showdiff=[
        app_commands.Choice(name="Yes", value="yes"),
        app_commands.Choice(name="No", value="no")
    ])
    async def exportexcel(self, interaction, category: app_commands.Choice[str], showdiff: app_commands.Choice[str] = None):
        session = SessionLocal()
        try:
            names = session.query(Name).all()
            if not names:
                await interaction.response.send_message("⚠️ No data to export.", ephemeral=True)
                return

            data = []
            for n in names:
                val = n.kill_score if category.value == "kill" else n.vs_score
                if showdiff and showdiff.value == "yes":
                    latest = session.query(ScoreHistory).filter_by(name_id=n.id, category=category.value).order_by(ScoreHistory.timestamp.desc()).first()
                    prev = session.query(ScoreHistory).filter_by(name_id=n.id, category=category.value).order_by(ScoreHistory.timestamp.desc()).offset(1).first()
                    if latest and prev:
                        diff = latest.value - prev.value
                    else:
                        diff = latest.value if latest else 0
                    data.append({"Name": n.name, "Score": val, "Δ": diff})
                else:
                    data.append({"Name": n.name, "Score": val})

            df = pd.DataFrame(data)
            output = BytesIO()
            df.to_excel(output, index=False)
            output.seek(0)
            await interaction.response.send_message(file=discord.File(output, filename=f"{category.value}_scores.xlsx"))
        finally:
            session.close()

    # ---------- Import Excel ----------
    @app_commands.command(name="importexcel", description="Import scores from Excel (Admin only)")
    @app_commands.describe(category="kill or vs", showdiff="Expect diff column?")
    @app_commands.choices(showdiff=[
        app_commands.Choice(name="Yes", value="yes"),
        app_commands.Choice(name="No", value="no")
    ])
    async def importexcel(self, interaction, category: str, attachment: discord.Attachment, showdiff: app_commands.Choice[str] = None):
        session = SessionLocal()
        try:
            file_bytes = await attachment.read()
            df = pd.read_excel(BytesIO(file_bytes))
            updated, ignored = 0, 0

            for _, row in df.iterrows():
                name = str(row["Name"])
                score_cell = str(row["Score"]).strip()
                # Strip parenthesized diff when present
                if "(" in score_cell:
                    score_cell = score_cell.split("(")[0].strip()

                try:
                    val = int(float(score_cell))
                except:
                    continue

                name_obj = session.query(Name).filter_by(name=name).first()
                if not name_obj:
                    name_obj = Name(name=name)
                    if category.lower() == "kill":
                        name_obj.kill_score = val
                    else:
                        name_obj.vs_score = val
                    session.add(name_obj)
                    updated += 1
                else:
                    prev_val = name_obj.kill_score if category.lower() == "kill" else name_obj.vs_score
                    if val > prev_val:
                        if category.lower() == "kill":
                            name_obj.kill_score = val
                        else:
                            name_obj.vs_score = val
                        updated += 1
                    else:
                        ignored += 1

            session.commit()
            await interaction.response.send_message(f"✅ Imported into {category}. Updated: {updated}, Ignored: {ignored}", ephemeral=True)
        finally:
            session.close()


async def setup(bot):
    await bot.add_cog(ExportImportCog(bot))

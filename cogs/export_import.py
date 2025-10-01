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
    @app_commands.describe(category="Choose score type to export")
    @app_commands.choices(category=[
        app_commands.Choice(name="Kill Score", value="kill"),
        app_commands.Choice(name="VS Score", value="vs")
    ])
    async def exportcsv(self, interaction, category: app_commands.Choice[str]):
        session = SessionLocal()
        try:
            names = session.query(Name).all()
            if not names:
                await interaction.response.send_message("⚠️ No data to export.", ephemeral=True)
                return

            output = BytesIO()
            writer = csv.writer(output)
            writer.writerow(["Name", "Score"])
            for n in names:
                val = n.kill_score if category.value == "kill" else n.vs_score
                writer.writerow([n.name, f"{val:,}"])
            output.seek(0)
            await interaction.response.send_message(file=discord.File(output, filename=f"{category.value}_scores.csv"))
        finally:
            session.close()

    # ---------- Import CSV ----------
    @app_commands.command(name="importcsv", description="Import scores from a CSV file (Admin only)")
    async def importcsv(self, interaction, category: str, attachment: discord.Attachment):
        session = SessionLocal()
        try:
            file_bytes = await attachment.read()
            lines = file_bytes.decode("utf-8").splitlines()
            reader = csv.reader(lines)
            next(reader, None)  # Skip header
            updated, ignored = 0, 0

            for row in reader:
                if len(row) == 2:
                    name, val = row
                    val = int(val.replace(',', ''))
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
            await interaction.response.send_message(
                f"✅ Imported into {category}. Updated: {updated}, Ignored: {ignored}", ephemeral=True
            )
        finally:
            session.close()

    # ---------- Export Excel ----------
    @app_commands.command(name="exportexcel", description="Export scores to Excel")
    @app_commands.describe(category="Choose score type to export")
    @app_commands.choices(category=[
        app_commands.Choice(name="Kill Score", value="kill"),
        app_commands.Choice(name="VS Score", value="vs")
    ])
    async def exportexcel(self, interaction, category: app_commands.Choice[str]):
        session = SessionLocal()
        try:
            names = session.query(Name).all()
            if not names:
                await interaction.response.send_message("⚠️ No data to export.", ephemeral=True)
                return

            data = []
            for n in names:
                val = n.kill_score if category.value == "kill" else n.vs_score
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
    async def importexcel(self, interaction, category: str, attachment: discord.Attachment):
        session = SessionLocal()
        try:
            file_bytes = await attachment.read()
            df = pd.read_excel(BytesIO(file_bytes))
            updated, ignored = 0, 0

            for _, row in df.iterrows():
                name = str(row["Name"])
                val = int(row["Score"])
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
            await interaction.response.send_message(
                f"✅ Imported into {category}. Updated: {updated}, Ignored: {ignored}", ephemeral=True
            )
        finally:
            session.close()


async def setup(bot):
    await bot.add_cog(ExportImportCog(bot))

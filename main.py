# ---------- FILE: main.py ----------
import os
import threading
from flask import Flask
import discord
from discord.ext import commands

from config import TOKEN
from database import Base, engine
from cogs import translation, scoring, export_import, utilities
# Added allcommands cog
from cogs import allcommands

# ---------- Flask Setup ----------
app = Flask(__name__)

@app.route("/")
def home():
    return "Bot is alive!"

def run_flask():
    app.run(host="0.0.0.0", port=5000)

# ---------- Discord Bot Setup ----------
intents = discord.Intents.default()
intents.messages = True
intents.message_content = True
intents.reactions = True

bot = commands.Bot(command_prefix="!", intents=intents)

# ---------- Load Cogs ----------
async def load_cogs():
    await bot.add_cog(translation.TranslationCog(bot))
    await bot.add_cog(scoring.ScoringCog(bot))
    await bot.add_cog(export_import.ExportImportCog(bot))
    await bot.add_cog(utilities.UtilitiesCog(bot))
    await bot.add_cog(allcommands.AllCommandsCog(bot))  # Load allcommands cog

# ---------- Events ----------
@bot.event
async def on_ready():
    try:
        await load_cogs()
        synced = await bot.tree.sync()
        print(f"✅ Synced {len(synced)} commands")
    except Exception as e:
        print(f"❌ Sync failed: {e}")
    print(f"🤖 Logged in as {bot.user}")

# ---------- Main ----------
if __name__ == "__main__":
    Base.metadata.create_all(engine)

    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()

    bot.run(TOKEN)

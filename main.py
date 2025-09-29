import os
import threading
import logging
from flask import Flask
import discord
from discord.ext import commands

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("discordbot")

TOKEN = os.getenv("TOKEN")

app = Flask(__name__)
@app.route("/")
def home():
    return "Bot is alive!"

def run_flask():
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))

intents = discord.Intents.default()
intents.messages = True
intents.message_content = True
intents.reactions = True

bot = commands.Bot(command_prefix="!", intents=intents)

try:
    from database import init_db, SessionLocal
    import commands as command_module
    import utils
except Exception as e:
    logger.exception("Failed to import modules: %s", e)
    raise

init_db()

# Register all commands
command_module.setup(bot, SessionLocal)

# Translator commands
command_module.setup_translator(bot.tree)

@bot.event
async def on_ready():
    try:
        synced = await bot.tree.sync()
        logger.info("Synced %d commands", len(synced))
    except Exception as e:
        logger.exception("Command sync failed: %s", e)
    logger.info("Bot logged in as %s (ID: %s)", bot.user, bot.user.id)

if __name__ == "__main__":
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    logger.info("Flask server started")

    if not TOKEN:
        logger.error("TOKEN not set. Exiting.")
        raise SystemExit("TOKEN not set.")
    bot.run(TOKEN)

# ---------- main.py ----------
import os
import threading
import logging
from flask import Flask
import discord
from discord.ext import commands

# Configure basic logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s"
)
logger = logging.getLogger("discordbot")

# Environment
TOKEN = os.getenv("TOKEN")  # Discord bot token must be set in env

# Flask health check
app = Flask(__name__)

@app.route("/")
def home():
    return "Bot is alive!"

def run_flask():
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))

# Discord intents and bot
intents = discord.Intents.default()
intents.messages = True
intents.message_content = True
intents.reactions = True

bot = commands.Bot(command_prefix="!", intents=intents)

# Import local modules
try:
    from database import init_db, SessionLocal
    import commands as command_module
    import utils
except Exception as e:
    logger.exception("Failed to import project modules: %s", e)
    raise

# Initialize DB
init_db()

# Register commands
try:
    command_module.setup(bot, SessionLocal)
except Exception as e:
    logger.exception("Failed to setup commands: %s", e)
    raise

@bot.event
async def on_ready():
    try:
        synced = await bot.tree.sync()
        logger.info("Synced %d commands", len(synced))
    except Exception as e:
        logger.exception("Command sync failed: %s", e)
    logger.info("Bot logged in as %s (ID: %s)", bot.user, bot.user.id)

if __name__ == "__main__":
    # Start Flask in a separate thread
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    logger.info("Flask health server started")

    # Run bot
    if not TOKEN:
        logger.error("TOKEN environment variable not set. Exiting.")
        raise SystemExit("TOKEN environment variable not set.")
    try:
        bot.run(TOKEN)
    except Exception as e:
        logger.exception("Bot failed to start: %s", e)
        raise

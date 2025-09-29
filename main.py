# ---------- main.py — PART 1: bootstrap, Flask, bot startup ----------
# Copy this file first. It expects database.py, models.py, utils.py, commands.py in the same folder.

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
    # Bind to all interfaces for hosting (Render, etc.)
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))

# Discord intents and bot
intents = discord.Intents.default()
intents.messages = True
intents.message_content = True
intents.reactions = True

bot = commands.Bot(command_prefix="!", intents=intents)

# Import local modules (they will be provided in following parts)
# These imports are placed after bot creation to avoid circular import issues in some environments.
try:
    from database import init_db, SessionLocal
    import commands as command_module   # module with slash command registration
    import utils
except Exception as e:
    logger.exception("Failed to import project modules: %s", e)
    raise

# Initialize DB (creates tables if missing)
init_db()

# Provide session factory on utils/commands modules (they can call SessionLocal())
# If you prefer a single global session, modules should call SessionLocal() themselves.
# Here we do not create a long-lived session to avoid cross-thread issues; commands use short sessions.
utils.set_session_factory(SessionLocal)

# Register events / commands
# The commands.py module will expose a setup(bot) function that registers slash commands and handlers.
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
    # Start Flask in a separate thread so this process stays alive on hosting platforms
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

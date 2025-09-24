import discord
from discord import app_commands
from discord.ext import commands
import os
import json
import requests
from threading import Thread
from flask import Flask

# -------------------
# Flask setup (dummy web server)
# -------------------
app = Flask("")

@app.route("/")
def home():
    return "Bot is running!"

def run_flask():
    app.run(host="0.0.0.0", port=5000)

Thread(target=run_flask).start()  # Run Flask in a separate thread

# -------------------
# Discord bot setup
# -------------------
intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="/", intents=intents)
tree = bot.tree  # app_commands tree

CONFIG_FILE = "config.json"

# Load or create config
if not os.path.isfile(CONFIG_FILE):
    with open(CONFIG_FILE, "w") as f:
        json.dump({"translate_channel_id": None}, f)

with open(CONFIG_FILE, "r") as f:
    config = json.load(f)

HF_API_KEY = os.environ["HF_API_KEY"]
DISCORD_TOKEN = os.environ["DISCORD_TOKEN"]

# Translation function
def translate_text(text):
    if any("а" <= c <= "я" or c in "іїєґ" for c in text.lower()):
        model = "Helsinki-NLP/opus-mt-uk-en"
        prefix = "🇺🇦 ➝ 🇺🇸"
    else:
        model = "Helsinki-NLP/opus-mt-en-uk"
        prefix = "🇺🇸 ➝ 🇺🇦"

    payload = {"inputs": text}
    headers = {"Authorization": f"Bearer {HF_API_KEY}"}

    try:
        response = requests.post(
            f"https://api-inference.huggingface.co/models/{model}",
            headers=headers,
            json=payload,
            timeout=10
        )
        response.raise_for_status()
        result = response.json()
        translated = result[0]["translation_text"]
        return f"{prefix}: {translated}"
    except Exception:
        return "⚠️ Translation unavailable, please try again."

# Slash commands
@tree.command(name="setchannel", description="Set the translation channel")
@app_commands.describe(channel="The channel to translate messages in")
async def setchannel(interaction: discord.Interaction, channel: discord.TextChannel):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ You must be an admin to do this.", ephemeral=True)
        return

    config["translate_channel_id"] = channel.id
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f)
    await interaction.response.send_message(f"✅ Translation channel set to {channel.mention}")

@tree.command(name="unsetchannel", description="Unset the translation channel")
async def unsetchannel(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ You must be an admin to do this.", ephemeral=True)
        return

    config["translate_channel_id"] = None
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f)
    await interaction.response.send_message("✅ Translation channel cleared")

@tree.command(name="status", description="Show the current translation channel")
async def status(interaction: discord.Interaction):
    channel_id = config.get("translate_channel_id")
    if channel_id:
        channel = bot.get_channel(channel_id)
        await interaction.response.send_message(f"Current translation channel: {channel.mention}")
    else:
        await interaction.response.send_message("No translation channel set.")

# On message event
@bot.event
async def on_message(message):
    if message.author.bot:
        return

    channel_id = config.get("translate_channel_id")
    if channel_id and message.channel.id == channel_id:
        translated = translate_text(message.content)
        await message.channel.send(translated)

    await bot.process_commands(message)

# On ready
@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"🤖 {bot.user} is online and ready!")

# Run bot
bot.run(DISCORD_TOKEN)

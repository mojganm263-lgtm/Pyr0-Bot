import discord
from discord.ext import commands
import os
import json
import requests

# Intents
intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="/", intents=intents)

CONFIG_FILE = "config.json"

# Load or create config
if not os.path.isfile(CONFIG_FILE):
    with open(CONFIG_FILE, "w") as f:
        json.dump({"translate_channel_id": None}, f)

with open(CONFIG_FILE, "r") as f:
    config = json.load(f)

HF_API_KEY = os.environ["HF_API_KEY"]
DISCORD_TOKEN = os.environ["DISCORD_TOKEN"]

# Function to detect language and translate
def translate_text(text):
    url = "https://api-inference.huggingface.co/models/Helsinki-NLP/opus-mt-en-uk"
    headers = {"Authorization": f"Bearer {HF_API_KEY}"}

    # Detect English letters for simplicity
    if any("а" <= c <= "я" or c in "іїєґ" for c in text.lower()):
        # Ukrainian → English
        model = "Helsinki-NLP/opus-mt-uk-en"
        prefix = "🇺🇦 ➝ 🇺🇸"
    else:
        # English → Ukrainian
        model = "Helsinki-NLP/opus-mt-en-uk"
        prefix = "🇺🇸 ➝ 🇺🇦"

    payload = {"inputs": text}
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
@bot.slash_command(name="setchannel", description="Set the translation channel")
async def setchannel(ctx, channel: discord.TextChannel):
    if not ctx.author.guild_permissions.administrator:
        await ctx.respond("❌ You must be an admin to do this.", ephemeral=True)
        return

    config["translate_channel_id"] = channel.id
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f)
    await ctx.respond(f"✅ Translation channel set to {channel.mention}")

@bot.slash_command(name="unsetchannel", description="Unset the translation channel")
async def unsetchannel(ctx):
    if not ctx.author.guild_permissions.administrator:
        await ctx.respond("❌ You must be an admin to do this.", ephemeral=True)
        return

    config["translate_channel_id"] = None
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f)
    await ctx.respond("✅ Translation channel cleared")

@bot.slash_command(name="status", description="Show the current translation channel")
async def status(ctx):
    channel_id = config.get("translate_channel_id")
    if channel_id:
        channel = bot.get_channel(channel_id)
        await ctx.respond(f"Current translation channel: {channel.mention}")
    else:
        await ctx.respond("No translation channel set.")

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
    print(f"🤖 {bot.user} is online and ready!")

bot.run(DISCORD_TOKEN)
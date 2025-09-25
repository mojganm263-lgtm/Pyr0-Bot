import discord
from discord.ext import commands
from discord import app_commands
import json
import threading
from flask import Flask
import requests
import os

# -------------------------
# Minimal Flask server for Render
# -------------------------
app = Flask("")

@app.route("/")
def home():
    return "OK"

def run_flask():
    app.run(host="0.0.0.0", port=8080)

threading.Thread(target=run_flask, daemon=True).start()

# -------------------------
# Bot setup
# -------------------------
intents = discord.Intents.default()
intents.messages = True
intents.message_content = True

bot = commands.Bot(command_prefix="/", intents=intents)
bot.remove_command("help")

DATA_FILE = "data.json"

# -------------------------
# Helper functions
# -------------------------
def load_data():
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {"channels": {}, "entries": {}}

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def detect_language(text: str):
    """Detect the language of a given text using Hugging Face."""
    HF_API = os.environ.get("HF_KEY")
    headers = {"Authorization": f"Bearer {HF_API}"}
    payload = {"inputs": text}
    model = "papluca/xlm-roberta-base-language-detection"
    response = requests.post(
        f"https://api-inference.huggingface.co/models/{model}",
        headers=headers,
        json=payload,
    )
    try:
        result = response.json()
        if isinstance(result, list) and result:
            best = max(result[0], key=lambda x: x["score"])
            return best["label"]
    except Exception:
        return None
    return None

def translate_text(text: str, source: str, target: str):
    """Translate from source to target language using Hugging Face."""
    HF_API = os.environ.get("HF_KEY")
    headers = {"Authorization": f"Bearer {HF_API}"}
    payload = {"inputs": text}
    model = f"Helsinki-NLP/opus-mt-{source}-{target}"
    response = requests.post(
        f"https://api-inference.huggingface.co/models/{model}",
        headers=headers,
        json=payload,
    )
    try:
        result = response.json()
        if isinstance(result, list) and "translation_text" in result[0]:
            return result[0]["translation_text"]
    except Exception:
        return text
    return text

# -------------------------
# Bot events
# -------------------------
@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"Logged in as {bot.user} ({bot.user.id})")
    print(f"Connected guilds: {[g.name for g in bot.guilds]}")

@bot.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return

    data = load_data()
    config = data["channels"].get(str(message.channel.id))

    if config:
        source = config.get("source")
        target = config.get("target")
        detected = detect_language(message.content)

        if detected == source:
            translated = translate_text(message.content, source, target)
            await message.channel.send(f"🌐 {message.author.display_name} ({target}): {translated}")
        elif detected == target:
            translated = translate_text(message.content, target, source)
            await message.channel.send(f"🌐 {message.author.display_name} ({source}): {translated}")

    await bot.process_commands(message)

# -------------------------
# Slash commands
# -------------------------
@bot.tree.command(name="setchannel", description="Set translation pair for this channel")
@app_commands.describe(source="Source language code", target="Target language code")
async def set_channel(interaction: discord.Interaction, source: str, target: str):
    data = load_data()
    data["channels"][str(interaction.channel.id)] = {"source": source, "target": target}
    save_data(data)
    await interaction.response.send_message(
        f"Channel set for translations: {source} ↔ {target}", ephemeral=True
    )

@bot.tree.command(name="commands", description="Show bot commands")
async def commands_list(interaction: discord.Interaction):
    cmds = [
        "/setchannel [source] [target] - set translation pair for channel",
        "/commands - show commands",
        "/addentry [name] [number] - add a number to a name",
        "/showtable [name/all] - display numbers table",
        "/removeentry [name] - remove entries for a name",
    ]
    await interaction.response.send_message("\n".join(cmds), ephemeral=True)

# -------------------------
# Prefix commands (unchanged)
# -------------------------
@bot.command()
async def addentry(ctx, name: str, number: float):
    data = load_data()
    entries = data.get("entries", {})
    entries.setdefault(name, []).append(
        {"value": number, "timestamp": ctx.message.created_at.isoformat()}
    )
    data["entries"] = entries
    save_data(data)
    await ctx.send(f"Added {number} to {name}")

@bot.command()
async def showtable(ctx, name: str):
    data = load_data()
    entries = data.get("entries", {})
    if name == "all":
        text = ""
        for n, vals in entries.items():
            text += f"{n}: {[v['value'] for v in vals]}\n"
        await ctx.send(f"```\n{text}\n```")
    else:
        vals = entries.get(name, [])
        await ctx.send(f"{name}: {[v['value'] for v in vals]}")

@bot.command()
async def removeentry(ctx, name: str):
    data = load_data()
    entries = data.get("entries", {})
    if name in entries:
        del entries[name]
        data["entries"] = entries
        save_data(data)
        await ctx.send(f"Removed all entries for {name}")
    else:
        await ctx.send(f"No entries found for {name}")

# -------------------------
# Run bot
# -------------------------
TOKEN = os.environ.get("TOKEN")
if not TOKEN:
    print("ERROR: TOKEN environment variable is missing!")
else:
    bot.run(TOKEN)

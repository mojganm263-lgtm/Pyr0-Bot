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
    # Flask runs in a separate thread to keep the bot alive on Render
    app.run(host="0.0.0.0", port=8080)

threading.Thread(target=run_flask, daemon=True).start()

# -------------------------
# Bot setup
# -------------------------
intents = discord.Intents.default()
intents.messages = True
intents.reactions = True
intents.message_content = True  # required to read messages

bot = commands.Bot(command_prefix="/", intents=intents)
bot.remove_command("help")  # remove default help command

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

def translate_text(text, target_lang):
    HF_API = os.environ.get("HF_KEY")
    model = "Helsinki-NLP/opus-mt-en-ROMANCE"
    headers = {"Authorization": f"Bearer {HF_API}"}
    payload = {"inputs": text}
    response = requests.post(f"https://api-inference.huggingface.co/models/{model}", headers=headers, json=payload)
    result = response.json()
    if isinstance(result, list) and "translation_text" in result[0]:
        return result[0]["translation_text"]
    return text

# -------------------------
# Bot events
# -------------------------
@bot.event
async def on_ready():
    # Sync slash commands
    await bot.tree.sync()
    print(f"Logged in as {bot.user} ({bot.user.id})")
    print(f"Connected guilds: {[g.name for g in bot.guilds]}")

# -------------------------
# Slash commands
# -------------------------
@bot.tree.command(name="setchannel", description="Set translation channel")
@app_commands.describe(lang="Language: uk/en/ko")
async def set_channel(interaction: discord.Interaction, lang: str):
    data = load_data()
    data["channels"][str(interaction.channel.id)] = lang
    save_data(data)
    await interaction.response.send_message(f"Channel set for {lang} translation", ephemeral=True)

@bot.tree.command(name="commands", description="Show bot commands")
async def commands_list(interaction: discord.Interaction):
    cmds = [
        "/setchannel [lang] - set translation channel",
        "/commands - show commands",
        "/addentry [name] [number] - add a number to a name",
        "/showtable [name/all] - display numbers table",
        "/removeentry [name] - remove entries for a name",
    ]
    await interaction.response.send_message("\n".join(cmds), ephemeral=True)

# -------------------------
# Prefix commands
# -------------------------
@bot.command()
async def addentry(ctx, name: str, number: float):
    data = load_data()
    entries = data.get("entries", {})
    entries.setdefault(name, []).append({"value": number, "timestamp": ctx.message.created_at.isoformat()})
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
# Reaction translation
# -------------------------
@bot.event
async def on_reaction_add(reaction, user):
    data = load_data()
    lang = data["channels"].get(str(reaction.message.channel.id))
    if lang and user != bot.user:
        translated = translate_text(reaction.message.content, lang)
        await reaction.message.channel.send(f"{user.display_name} translated: {translated}")

# -------------------------
# Run bot
# -------------------------
TOKEN = os.environ.get("TOKEN")  # Render environment variable
if not TOKEN:
    print("ERROR: TOKEN environment variable is missing!")
else:
    bot.run(TOKEN)

import discord
from discord.ext import commands
from discord import app_commands
import json
import threading
from flask import Flask
import requests
import os
import matplotlib.pyplot as plt

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

bot = commands.Bot(command_prefix="!", intents=intents)  # ! only for dev, slash commands are main
bot.remove_command("help")

DATA_FILE = "data.json"

# -------------------------
# Language mapping
# -------------------------
LANG_MAP = {
    "en": "english",
    "uk": "ukrainian",
    "ko": "korean",
    "pt": "portuguese"
}
REVERSE_LANG_MAP = {v: k for k, v in LANG_MAP.items()}

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
    HF_API = os.environ.get("HF_KEY")
    headers = {"Authorization": f"Bearer {HF_API}"}
    payload = {"inputs": text}
    model = "papluca/xlm-roberta-base-language-detection"
    response = requests.post(f"https://api-inference.huggingface.co/models/{model}", headers=headers, json=payload)
    try:
        result = response.json()
        if isinstance(result, list) and result:
            best = max(result[0], key=lambda x: x["score"])
            return best["label"].lower()
    except Exception:
        return None
    return None

def translate_text(text: str, source: str, target: str):
    HF_API = os.environ.get("HF_KEY")
    headers = {"Authorization": f"Bearer {HF_API}"}
    payload = {"inputs": text}
    model = f"Helsinki-NLP/opus-mt-{source}-{target}"
    response = requests.post(f"https://api-inference.huggingface.co/models/{model}", headers=headers, json=payload)
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
    print(f"✅ Logged in as {bot.user} ({bot.user.id})")

@bot.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return

    data = load_data()
    config = data["channels"].get(str(message.channel.id))

    if config:
        source = config.get("source")  # e.g. "uk"
        target = config.get("target")  # e.g. "en"
        detected = detect_language(message.content)

        if not detected:
            return

        # Map detection result to code
        detected_code = REVERSE_LANG_MAP.get(detected)

        if detected_code == source:
            translated = translate_text(message.content, source, target)
            await message.reply(f"🌐 {message.author.display_name} ({target}): {translated}")
        elif detected_code == target:
            translated = translate_text(message.content, target, source)
            await message.reply(f"🌐 {message.author.display_name} ({source}): {translated}")

    await bot.process_commands(message)

# -------------------------
# Slash commands
# -------------------------
@bot.tree.command(name="setchannel", description="Set translation pair for this channel")
@app_commands.choices(
    source=[
        app_commands.Choice(name="English", value="en"),
        app_commands.Choice(name="Korean", value="ko"),
        app_commands.Choice(name="Ukrainian", value="uk"),
        app_commands.Choice(name="Portuguese", value="pt"),
    ],
    target=[
        app_commands.Choice(name="English", value="en"),
        app_commands.Choice(name="Korean", value="ko"),
        app_commands.Choice(name="Ukrainian", value="uk"),
        app_commands.Choice(name="Portuguese", value="pt"),
    ]
)
async def set_channel(interaction: discord.Interaction, source: app_commands.Choice[str], target: app_commands.Choice[str]):
    data = load_data()
    data["channels"][str(interaction.channel.id)] = {"source": source.value, "target": target.value}
    save_data(data)
    await interaction.response.send_message(f"✅ Channel set: {source.name} ↔ {target.name}", ephemeral=True)

@bot.tree.command(name="addentry", description="Add a number to a name")
async def addentry(interaction: discord.Interaction, name: str, number: float):
    data = load_data()
    entries = data.get("entries", {})
    entries.setdefault(name, []).append({"value": number, "timestamp": interaction.created_at.isoformat()})
    data["entries"] = entries
    save_data(data)
    await interaction.response.send_message(f"Added {number} to {name}")

@bot.tree.command(name="showtable", description="Show table of numbers")
async def showtable(interaction: discord.Interaction, name: str):
    data = load_data()
    entries = data.get("entries", {})
    if name == "all":
        text = "\n".join([f"{n}: {[v['value'] for v in vals]}" for n, vals in entries.items()])
        await interaction.response.send_message(f"```\n{text}\n```")
    else:
        vals = entries.get(name, [])
        await interaction.response.send_message(f"{name}: {[v['value'] for v in vals]}")

@bot.tree.command(name="showgraph", description="Show graph of numbers")
async def showgraph(interaction: discord.Interaction, name: str):
    data = load_data()
    entries = data.get("entries", {})
    vals = []
    if name == "all":
        for n, v in entries.items():
            vals.extend([x["value"] for x in v])
    else:
        vals = [x["value"] for x in entries.get(name, [])]

    if not vals:
        await interaction.response.send_message("No data to graph.")
        return

    plt.figure()
    plt.plot(vals, marker="o")
    plt.title(f"Values for {name}")
    plt.xlabel("Entry")
    plt.ylabel("Value")
    plt.savefig("graph.png")
    plt.close()

    await interaction.response.send_message(file=discord.File("graph.png"))

@bot.tree.command(name="removeentry", description="Remove all entries for a name")
async def removeentry(interaction: discord.Interaction, name: str):
    data = load_data()
    entries = data.get("entries", {})
    if name in entries:
        del entries[name]
        data["entries"] = entries
        save_data(data)
        await interaction.response.send_message(f"Removed all entries for {name}")
    else:
        await interaction.response.send_message(f"No entries found for {name}")

# -------------------------
# Run bot
# -------------------------
TOKEN = os.environ.get("TOKEN")
if not TOKEN:
    print("ERROR: TOKEN environment variable is missing!")
else:
    bot.run(TOKEN)

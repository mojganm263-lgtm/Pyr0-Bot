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

bot = commands.Bot(command_prefix="!", intents=intents)
bot.remove_command("help")

DATA_FILE = "data.json"
SUPPORTED_LANGS = ["en", "uk", "ko", "pt"]

# -------------------------
# Helper functions
# -------------------------
def load_data():
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {"channels": {}, "reverse_channels": [], "entries": {}}

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def detect_language(text: str):
    text = text.strip()
    if not text:
        return None
    HF_API = os.environ.get("HF_KEY")
    if not HF_API:
        print("⚠️ HF_KEY missing")
        return None
    headers = {"Authorization": f"Bearer {HF_API}"}
    payload = {"inputs": text}
    model = "papluca/xlm-roberta-base-language-detection"
    try:
        response = requests.post(
            f"https://api-inference.huggingface.co/models/{model}",
            headers=headers,
            json=payload,
            timeout=10
        )
        result = response.json()
        if isinstance(result, list) and result:
            best = max(result[0], key=lambda x: x["score"])
            detected = best["label"].lower().strip()
            code_map = {"english": "en", "ukrainian": "uk", "korean": "ko", "portuguese": "pt",
                        "en": "en", "uk": "uk", "ko": "ko", "pt": "pt"}
            return code_map.get(detected)
    except Exception as e:
        print(f"⚠️ Language detection error: {e}")
    return None

def translate_text(text: str, source: str, target: str):
    text = text.strip()
    if not text or source == target:
        return text
    HF_API = os.environ.get("HF_KEY")
    if not HF_API:
        print("⚠️ HF_KEY missing")
        return text
    headers = {"Authorization": f"Bearer {HF_API}"}
    payload = {"inputs": text}
    model = f"Helsinki-NLP/opus-mt-{source}-{target}"
    try:
        response = requests.post(
            f"https://api-inference.huggingface.co/models/{model}",
            headers=headers,
            json=payload,
            timeout=15
        )
        result = response.json()
        if isinstance(result, list) and "translation_text" in result[0]:
            translated = result[0]["translation_text"]
            print(f"🌐 Translation ({source}->{target}): {translated}")
            return translated
    except Exception as e:
        print(f"⚠️ Translation error ({source}->{target}): {e}")
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
    if message.author.bot or not message.content.strip():
        return

    data = load_data()
    langs = data["channels"].get(str(message.channel.id))
    reverse_channels = data.get("reverse_channels", [])

    if not langs and str(message.channel.id) not in reverse_channels:
        return

    detected_code = detect_language(message.content)
    if not detected_code:
        print("⚠️ Could not detect language")
        return

    if detected_code not in SUPPORTED_LANGS:
        print(f"⚠️ Detected language '{detected_code}' not supported")
        return

    # Standard two-way translation
    if langs and detected_code in langs:
        target = langs[1] if detected_code == langs[0] else langs[0]
        translated = translate_text(message.content, detected_code, target)
        await message.reply(f"🌐 {message.author.display_name} ({target}): {translated}")
        print(f"Translated in channel {message.channel.id} from {detected_code} to {target}")

    # Reverse translation
    if str(message.channel.id) in reverse_channels:
        target = langs[0] if langs else "en"
        if detected_code != target:
            translated = translate_text(message.content, detected_code, target)
            await message.reply(f"🔄 Reverse ({target}): {translated}")
            print(f"Reverse translated in channel {message.channel.id} from {detected_code} to {target}")

    await bot.process_commands(message)

# -------------------------
# Slash commands
# -------------------------
@bot.tree.command(name="setchannel", description="Set translation pair for this channel")
@app_commands.choices(
    lang1=[app_commands.Choice(name="English", value="en"),
           app_commands.Choice(name="Korean", value="ko"),
           app_commands.Choice(name="Ukrainian", value="uk"),
           app_commands.Choice(name="Portuguese", value="pt")],
    lang2=[app_commands.Choice(name="English", value="en"),
           app_commands.Choice(name="Korean", value="ko"),
           app_commands.Choice(name="Ukrainian", value="uk"),
           app_commands.Choice(name="Portuguese", value="pt")]
)
async def set_channel(interaction: discord.Interaction, lang1: app_commands.Choice[str], lang2: app_commands.Choice[str]):
    if lang1.value == lang2.value:
        await interaction.response.send_message("❌ You must pick two different languages.", ephemeral=True)
        return
    data = load_data()
    data["channels"][str(interaction.channel.id)] = [lang1.value, lang2.value]
    save_data(data)
    await interaction.response.send_message(f"✅ Translation pair set: {lang1.name} ↔ {lang2.name}", ephemeral=True)

@bot.tree.command(name="setreverse", description="Enable reverse translation for this channel")
async def set_reverse(interaction: discord.Interaction):
    data = load_data()
    reverse_channels = set(data.get("reverse_channels", []))
    reverse_channels.add(str(interaction.channel.id))
    data["reverse_channels"] = list(reverse_channels)
    save_data(data)
    await interaction.response.send_message("🔄 Reverse translation enabled for this channel.", ephemeral=True)

@bot.tree.command(name="removereverse", description="Disable reverse translation for this channel")
async def remove_reverse(interaction: discord.Interaction):
    data = load_data()
    reverse_channels = set(data.get("reverse_channels", []))
    reverse_channels.discard(str(interaction.channel.id))
    data["reverse_channels"] = list(reverse_channels)
    save_data(data)
    await interaction.response.send_message("🔄 Reverse translation disabled for this channel.", ephemeral=True)

@bot.tree.command(name="help", description="Show all commands")
async def help_cmd(interaction: discord.Interaction):
    commands_list = [
        "/setchannel [lang1] [lang2] - set translation pair",
        "/setreverse - enable reverse translation",
        "/removereverse - disable reverse translation",
        "/listchannels - show all translation channels",
        "/addentry [name] [number] - add number entry",
        "/showtable [name/all] - show entries",
        "/showgraph [name/all] - show graph",
        "/removeentry [name] - remove entries"
    ]
    await interaction.response.send_message("📜 Commands:\n" + "\n".join(commands_list), ephemeral=True)

@bot.tree.command(name="listchannels", description="Show all channels with translation settings")
async def list_channels(interaction: discord.Interaction):
    data = load_data()
    channels = data.get("channels", {})
    reverse_channels = set(data.get("reverse_channels", []))

    if not channels and not reverse_channels:
        await interaction.response.send_message("📭 No channels are configured for translation.", ephemeral=True)
        return

    lines = []
    for ch_id, langs in channels.items():
        rev = " (Reverse)" if ch_id in reverse_channels else ""
        lines.append(f"<#{ch_id}>: {langs[0]} ↔ {langs[1]}{rev}")

    for ch_id in reverse_channels:
        if ch_id not in channels:
            lines.append(f"<#{ch_id}>: Reverse only")

    await interaction.response.send_message("🌐 Translation channels:\n" + "\n".join(lines), ephemeral=True)

# -------------------------
# Number tracking commands
# -------------------------
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

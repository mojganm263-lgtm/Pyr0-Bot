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
        return {"channels": {}, "entries": {}}

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

    def hf_translate(src, tgt, txt):
        model = f"Helsinki-NLP/opus-mt-{src}-{tgt}"
        payload = {"inputs": txt}
        try:
            response = requests.post(
                f"https://api-inference.huggingface.co/models/{model}",
                headers=headers,
                json=payload,
                timeout=20
            )
            result = response.json()
            if isinstance(result, list) and result and "translation_text" in result[0]:
                return result[0]["translation_text"]
            elif isinstance(result, dict) and "translation_text" in result:
                return result["translation_text"]
        except Exception as e:
            print(f"⚠️ Translation error ({src}->{tgt}): {e}")
        return None

    # Try direct translation first
    translated = hf_translate(source, target, text)
    if translated:
        print(f"🌐 Translation ({source}->{target}): {translated}")
        return translated

    # Fallback via English if needed
    if source != "en" and target != "en":
        intermediate = hf_translate(source, "en", text)
        if intermediate:
            translated = hf_translate("en", target, intermediate)
            if translated:
                print(f"🌐 Translation via English ({source}->{target}): {translated}")
                return translated

    print(f"⚠️ Could not translate ({source}->{target}), returning original text")
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

    if not langs:
        return

    detected_code = detect_language(message.content)
    if not detected_code:
        print("⚠️ Could not detect language")
        return

    if detected_code not in langs:
        print(f"⚠️ Detected language '{detected_code}' not in channel pair {langs}")
        return

    # Determine target for bidirectional translation
    target = langs[1] if detected_code == langs[0] else langs[0]

    translated = translate_text(message.content, detected_code, target)
    await message.reply(f"🌐 {message.author.display_name} ({target}): {translated}")
    print(f"Translated in channel {message.channel.id} from {detected_code} to {target}")

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

@bot.tree.command(name="help", description="Show all commands")
async def help_cmd(interaction: discord.Interaction):
    commands_list = [
        "/setchannel [lang1] [lang2] - set translation pair",
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

    if not channels:
        await interaction.response.send_message("📭 No channels are configured for translation.", ephemeral=True)
        return

    lines = []
    for ch_id, langs in channels.items():
        lines.append(f"<#{ch_id}>: {langs[0]} ↔ {langs[1]}")

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

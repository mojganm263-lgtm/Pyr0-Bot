# main.py
import os
import json
import threading
import requests
from flask import Flask
import discord
from discord.ext import commands
from discord import app_commands
from langdetect import detect, LangDetectException
from googletrans import Translator

# ---------- Environment Variables ----------
TOKEN = os.getenv("TOKEN")
HF_KEY = os.getenv("HF_KEY")  # Optional if rate-limited

# ---------- Flask Setup ----------
app = Flask(__name__)

@app.route("/")
def home():
    return "Bot is alive!"

def run_flask():
    app.run(host="0.0.0.0", port=5000)

# ---------- JSON Storage ----------
DATA_FILE = "data.json"

def load_data():
    try:
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return {"channels": {}}

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)

data = load_data()

# ---------- Translation Setup ----------
# Working Hugging Face models
HF_MODELS = {
    ("en", "uk"): "Helsinki-NLP/opus-mt-en-uk",
    ("uk", "en"): "Helsinki-NLP/opus-mt-uk-en",
    ("ko", "en"): "Helsinki-NLP/opus-mt-ko-en",
}

HF_HEADERS = {"Authorization": f"Bearer {HF_KEY}"} if HF_KEY else {}

# Google Translator for other pairs
translator = Translator()

def translate(text: str, src_lang: str, tgt_lang: str) -> str:
    # Use HF if model exists
    model_name = HF_MODELS.get((src_lang, tgt_lang))
    if model_name:
        payload = {"inputs": text}
        try:
            response = requests.post(
                f"https://api-inference.huggingface.co/models/{model_name}",
                headers=HF_HEADERS,
                json=payload,
                timeout=30
            )
            if response.status_code != 200:
                return f"HF Translation error: {response.status_code}"
            result = response.json()
            if isinstance(result, list) and "translation_text" in result[0]:
                return result[0]["translation_text"]
            else:
                return "HF Translation failed."
        except requests.exceptions.RequestException as e:
            return f"HF request failed: {e}"

    # Fallback to googletrans for other pairs
    try:
        translated = translator.translate(text, src=src_lang, dest=tgt_lang)
        return translated.text
    except Exception as e:
        return f"Google Translate failed: {e}"

# ---------- Discord Bot Setup ----------
intents = discord.Intents.default()
intents.messages = True
intents.message_content = True
intents.reactions = True
bot = commands.Bot(command_prefix="!", intents=intents)

# ---------- Admin Check ----------
def is_admin(interaction):
    return interaction.user.guild_permissions.administrator

# ---------- Slash Commands ----------
@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} commands")
    except Exception as e:
        print(f"Error syncing commands: {e}")

@bot.tree.command(name="setchannel", description="Set this channel as a bidirectional translator (Admin only)")
async def setchannel(interaction: discord.Interaction):
    if not is_admin(interaction):
        await interaction.response.send_message("❌ You must be an admin.", ephemeral=True)
        return

    cid = str(interaction.channel.id)
    if cid in data["channels"]:
        await interaction.response.send_message("⚠️ Channel already configured.", ephemeral=True)
        return

    data["channels"][cid] = {"lang1": "en", "lang2": "pt", "flags": ["🇺🇸", "🇵🇹"]}
    save_data(data)
    await interaction.response.send_message("✅ Channel set as translator: English ↔ Portuguese", ephemeral=True)

@bot.tree.command(name="removechannel", description="Remove this channel from translator mode (Admin only)")
async def removechannel(interaction: discord.Interaction):
    if not is_admin(interaction):
        await interaction.response.send_message("❌ Admins only.", ephemeral=True)
        return

    cid = str(interaction.channel.id)
    if cid not in data["channels"]:
        await interaction.response.send_message("⚠️ Channel not configured.", ephemeral=True)
        return

    data["channels"].pop(cid)
    save_data(data)
    await interaction.response.send_message("✅ Channel removed from translator mode.", ephemeral=True)

@bot.tree.command(name="listchannels", description="List all configured translator channels")
async def listchannels(interaction: discord.Interaction):
    if not data["channels"]:
        await interaction.response.send_message("⚠️ No channels configured.", ephemeral=True)
        return
    msg = "📚 **Translator Channels:**\n"
    for cid, info in data["channels"].items():
        msg += f"- <#{cid}>: {info['lang1']} ↔ {info['lang2']}\n"
    await interaction.response.send_message(msg, ephemeral=True)

@bot.tree.command(name="setlanguages", description="Set language pair (Admin only)")
@app_commands.choices(lang1=[
    app_commands.Choice(name="English", value="en"),
    app_commands.Choice(name="Ukrainian", value="uk"),
    app_commands.Choice(name="Korean", value="ko"),
    app_commands.Choice(name="Portuguese", value="pt")
])
@app_commands.choices(lang2=[
    app_commands.Choice(name="English", value="en"),
    app_commands.Choice(name="Ukrainian", value="uk"),
    app_commands.Choice(name="Korean", value="ko"),
    app_commands.Choice(name="Portuguese", value="pt")
])
async def setlanguages(interaction: discord.Interaction, lang1: app_commands.Choice[str], lang2: app_commands.Choice[str]):
    if not is_admin(interaction):
        await interaction.response.send_message("❌ Admins only.", ephemeral=True)
        return

    cid = str(interaction.channel.id)
    if cid not in data["channels"]:
        await interaction.response.send_message("⚠️ Channel not configured.", ephemeral=True)
        return

    data["channels"][cid]["lang1"] = lang1.value
    data["channels"][cid]["lang2"] = lang2.value
    save_data(data)
    await interaction.response.send_message(f"✅ Language pair updated: {lang1.name} ↔ {lang2.name}", ephemeral=True)

# ---------- Bidirectional Translation ----------
@bot.event
async def on_message(message):
    if message.author.bot:
        return

    cid = str(message.channel.id)
    if cid not in data["channels"]:
        return

    text = message.content.strip()
    if not text:
        return

    lang1 = data["channels"][cid]["lang1"]
    lang2 = data["channels"][cid]["lang2"]

    try:
        detected = detect(text)
    except LangDetectException:
        detected = lang1

    src, tgt = (lang1, lang2) if detected == lang1 else (lang2, lang1)
    translated = translate(text, src, tgt)
    await message.reply(f"🌐 Translation ({src} → {tgt}):\n{translated}")

# ---------- Flag Reaction Translation ----------
@bot.event
async def on_reaction_add(reaction, user):
    if user.bot:
        return

    emoji = str(reaction.emoji)
    msg = reaction.message

    flag_to_lang = {
        "🇺🇸": "en",
        "🇨🇦": "en",
        "🇺🇦": "uk",
        "🇰🇷": "ko",
        "🇵🇹": "pt"
    }

    if emoji not in flag_to_lang:
        return

    tgt = flag_to_lang[emoji]
    translated = translate(msg.content, "auto", tgt)
    await msg.reply(f"🌐 Translation ({tgt}):\n{translated}")

# ---------- Main Runner ----------
if __name__ == "__main__":
    threading.Thread(target=run_flask).start()
    bot.run(TOKEN)

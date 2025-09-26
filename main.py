# main.py
import os
import json
import threading
from flask import Flask
import discord
from discord.ext import commands
from discord import app_commands
from langdetect import detect, LangDetectException

# ---------- Transformers Setup ----------
import torch
from transformers import MarianMTModel, MarianTokenizer

# ---------- Environment Variables ----------
TOKEN = os.getenv("TOKEN")

# ---------- Flask Setup (Keep Render Awake) ----------
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

# ---------- Models Setup ----------
# Map short codes to Helsinki-NLP model names
MODEL_MAPPING = {
    ("en", "pt"): "Helsinki-NLP/opus-mt-en-pt",
    ("pt", "en"): "Helsinki-NLP/opus-mt-pt-en",
    ("en", "uk"): "Helsinki-NLP/opus-mt-en-uk",
    ("uk", "en"): "Helsinki-NLP/opus-mt-uk-en",
    ("en", "ko"): "Helsinki-NLP/opus-mt-en-ko",
    ("ko", "en"): "Helsinki-NLP/opus-mt-ko-en",
    ("pt", "uk"): "Helsinki-NLP/opus-mt-pt-uk",
    ("uk", "pt"): "Helsinki-NLP/opus-mt-uk-pt",
    ("pt", "ko"): "Helsinki-NLP/opus-mt-pt-ko",
    ("ko", "pt"): "Helsinki-NLP/opus-mt-ko-pt",
    ("uk", "ko"): "Helsinki-NLP/opus-mt-uk-ko",
    ("ko", "uk"): "Helsinki-NLP/opus-mt-ko-uk",
}

loaded_models = {}

def load_model(src, tgt):
    key = (src, tgt)
    if key in loaded_models:
        return loaded_models[key]
    if key not in MODEL_MAPPING:
        return None
    model_name = MODEL_MAPPING[key]
    tokenizer = MarianTokenizer.from_pretrained(model_name)
    model = MarianMTModel.from_pretrained(model_name)
    loaded_models[key] = (tokenizer, model)
    return tokenizer, model

def translate(text: str, src_lang: str, tgt_lang: str) -> str:
    model_pair = load_model(src_lang, tgt_lang)
    if model_pair is None:
        return f"❌ No model for {src_lang} → {tgt_lang}"
    tokenizer, model = model_pair
    inputs = tokenizer(text, return_tensors="pt", padding=True)
    try:
        translated = model.generate(**inputs)
        decoded = tokenizer.batch_decode(translated, skip_special_tokens=True)[0]
        return decoded
    except Exception as e:
        return f"Translation failed: {e}"

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
        await interaction.response.send_message("❌ You must be an admin to use this.", ephemeral=True)
        return
    channel_id = str(interaction.channel.id)
    if channel_id in data["channels"]:
        await interaction.response.send_message("⚠️ Already a translator channel.", ephemeral=True)
        return
    data["channels"][channel_id] = {"lang1": "en", "lang2": "pt", "flags": ["🇺🇸", "🇵🇹"]}
    save_data(data)
    await interaction.response.send_message(f"✅ Channel set as translator: English ↔ Portuguese", ephemeral=True)

@bot.tree.command(name="removechannel", description="Remove channel from translator mode (Admin only)")
async def removechannel(interaction: discord.Interaction):
    if not is_admin(interaction):
        await interaction.response.send_message("❌ Admin only.", ephemeral=True)
        return
    channel_id = str(interaction.channel.id)
    if channel_id not in data["channels"]:
        await interaction.response.send_message("⚠️ Not a translator channel.", ephemeral=True)
        return
    data["channels"].pop(channel_id)
    save_data(data)
    await interaction.response.send_message("✅ Channel removed.", ephemeral=True)

@bot.tree.command(name="listchannels", description="List all configured translator channels")
async def listchannels(interaction: discord.Interaction):
    if not data["channels"]:
        await interaction.response.send_message("⚠️ No translator channels.", ephemeral=True)
        return
    message = "📚 **Translator Channels:**\n"
    for cid, info in data["channels"].items():
        message += f"- <#{cid}>: {info['lang1']} ↔ {info['lang2']}\n"
    await interaction.response.send_message(message, ephemeral=True)

@bot.tree.command(name="setlanguages", description="Set language pair for this channel (Admin only)")
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
        await interaction.response.send_message("❌ Admin only.", ephemeral=True)
        return
    channel_id = str(interaction.channel.id)
    if channel_id not in data["channels"]:
        await interaction.response.send_message("⚠️ Use /setchannel first.", ephemeral=True)
        return
    data["channels"][channel_id]["lang1"] = lang1.value
    data["channels"][channel_id]["lang2"] = lang2.value
    save_data(data)
    await interaction.response.send_message(f"✅ Language pair updated: {lang1.name} ↔ {lang2.name}", ephemeral=True)

# ---------- Bidirectional Translation ----------
@bot.event
async def on_message(message):
    if message.author == bot.user:
        return
    channel_id = str(message.channel.id)
    if channel_id not in data["channels"]:
        return
    text = message.content.strip()
    if not text:
        return
    lang1 = data["channels"][channel_id]["lang1"]
    lang2 = data["channels"][channel_id]["lang2"]
    try:
        detected = detect(text)
    except LangDetectException:
        detected = lang1
    if detected == lang1:
        src_lang, tgt_lang = lang1, lang2
    else:
        src_lang, tgt_lang = lang2, lang1
    translated = translate(text, src_lang, tgt_lang)
    await message.reply(f"🌐 Translation ({src_lang} → {tgt_lang}):\n{translated}")

# ---------- Flag Reaction Translation ----------
@bot.event
async def on_reaction_add(reaction, user):
    if user.bot:
        return
    emoji = str(reaction.emoji)
    message = reaction.message
    flag_to_lang = {
        "🇺🇸": "en",
        "🇨🇦": "en",
        "🇺🇦": "uk",
        "🇰🇷": "ko",
        "🇵🇹": "pt"
    }
    if emoji not in flag_to_lang:
        return
    src_lang = "auto"
    tgt_lang = flag_to_lang[emoji]
    translated = translate(message.content, src_lang, tgt_lang)
    await message.reply(f"🌐 Translation ({tgt_lang}):\n{translated}")

# ---------- Main Runner ----------
if __name__ == "__main__":
    threading.Thread(target=run_flask).start()
    bot.run(TOKEN)

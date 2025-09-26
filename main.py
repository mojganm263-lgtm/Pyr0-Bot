# main.py
import os
import json
import threading
import requests
from flask import Flask
import discord
from discord.ext import commands

# ---------- Environment Variables ----------
TOKEN = os.getenv("TOKEN")
HF_KEY = os.getenv("HF_KEY")

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

# ---------- Hugging Face Translation ----------
HF_MODEL = "facebook/m2m100_418M"
HF_API_URL = f"https://api-inference.huggingface.co/models/{HF_MODEL}"
HF_HEADERS = {"Authorization": f"Bearer {HF_KEY}"}

def translate(text: str, src_lang: str, tgt_lang: str) -> str:
    payload = {
        "inputs": text,
        "parameters": {
            "source_lang": src_lang,
            "target_lang": tgt_lang
        }
    }
    response = requests.post(HF_API_URL, headers=HF_HEADERS, json=payload)
    if response.status_code != 200:
        return f"Translation error: {response.status_code}"
    try:
        return response.json()[0]["translation_text"]
    except (KeyError, IndexError, TypeError):
        return "Translation failed."

# ---------- Discord Bot Setup ----------
intents = discord.Intents.default()
intents.messages = True
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)  # prefix placeholder

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")

# Example placeholder: basic message listener
@bot.event
async def on_message(message):
    if message.author == bot.user:
        return
    # For now, just print messages in console
    print(f"Message from {message.author}: {message.content}")

# ---------- Main Runner ----------
if __name__ == "__main__":
    # Start Flask in a separate thread
    threading.Thread(target=run_flask).start()
    # Run Discord bot
    bot.run(TOKEN)

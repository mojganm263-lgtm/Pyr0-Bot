# ---------- PART 1: Imports, Environment, Flask, JSON, HF Models, Discord Setup ----------
import os
import json
import threading
import requests
import csv
from flask import Flask
import discord
from discord.ext import commands
from discord import app_commands
from langdetect import detect, LangDetectException
from googletrans import Translator
import matplotlib
matplotlib.use("Agg")  # Headless backend
import matplotlib.pyplot as plt
from io import BytesIO

# ---------- Environment Variables ----------
TOKEN = os.getenv("TOKEN")
HF_KEY = os.getenv("HF_KEY")  # Optional

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
        return {"channels": {}, "scores": {"kill": {}, "vs": {}}, "history": []}

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)

data = load_data()
scores = data.get("scores", {})
scores.setdefault("history", [])

translator = Translator()

# ---------- Hugging Face Models ----------
HF_MODELS = {
    ("en", "uk"): "Helsinki-NLP/opus-mt-en-uk",
    ("uk", "en"): "Helsinki-NLP/opus-mt-uk-en",
    ("ko", "en"): "Helsinki-NLP/opus-mt-ko-en",
    ("en", "ko"): "Helsinki-NLP/opus-mt-en-ko"
}
HF_HEADERS = {"Authorization": f"Bearer {HF_KEY}"} if HF_KEY else {}

# ---------- Discord Setup ----------
intents = discord.Intents.default()
intents.messages = True
intents.message_content = True
intents.reactions = True
bot = commands.Bot(command_prefix="!", intents=intents)

# ---------- PART 2: Translation Functions and Admin Check ----------
def translate(text: str, src: str, tgt: str) -> str:
    model_name = HF_MODELS.get((src, tgt))
    if model_name:
        try:
            response = requests.post(
                f"https://api-inference.huggingface.co/models/{model_name}",
                headers=HF_HEADERS,
                json={"inputs": text},
                timeout=30
            )
            if response.status_code == 200:
                result = response.json()
                if isinstance(result, list) and "translation_text" in result[0]:
                    return result[0]["translation_text"]
                return f"HF Translation failed ({response.status_code})"
        except requests.exceptions.RequestException as e:
            return f"HF request failed: {e}"
    try:
        translated = translator.translate(text, src=src, dest=tgt)
        return translated.text
    except Exception as e:
        return f"Google Translate failed: {e}"

def is_admin(interaction: discord.Interaction) -> bool:
    return interaction.user.guild_permissions.administrator

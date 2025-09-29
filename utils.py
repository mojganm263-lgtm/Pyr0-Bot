import logging
import discord
from discord import Interaction
import requests
from langdetect import detect
from googletrans import Translator as GoogleTranslator
from datetime import datetime
from sqlalchemy.orm import sessionmaker
from database import engine
from models import Score

# ----------------- Database session -----------------
SessionLocal = sessionmaker(bind=engine)

def get_session():
    return SessionLocal()

# ----------------- Translation helpers -----------------
HF_URL = "https://api-inference.huggingface.co/models/Helsinki-NLP/opus-mt-en-ROMANCE"
HF_HEADERS = {"Authorization": f"Bearer {None}"}  # Add token if available

google_translator = GoogleTranslator()

def translate_text(text: str, target_lang: str = "en") -> str:
    try:
        payload = {"inputs": text}
        resp = requests.post(HF_URL, headers=HF_HEADERS, json=payload, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            if isinstance(data, list) and len(data) > 0 and "translation_text" in data[0]:
                return data[0]["translation_text"]
    except Exception as e:
        logging.warning("HF translation failed: %s", e)

    try:
        translated = google_translator.translate(text, dest=target_lang)
        return translated.text
    except Exception as e:
        logging.error("Google Translate failed: %s", e)
        return text

# ----------------- Message helpers -----------------
async def send_long_message(interaction: Interaction, content: str, chunk_size: int = 1800):
    if not content:
        await interaction.response.send_message("No content to display.")
        return
    chunks = [content[i:i+chunk_size] for i in range(0, len(content), chunk_size)]
    first = True
    for chunk in chunks:
        if first:
            await interaction.response.send_message(chunk)
            first = False
        else:
            await interaction.followup.send(chunk)

# ----------------- Score helpers -----------------
def compute_diff(old_value: float, new_value: float) -> float:
    try:
        return round(new_value - old_value, 2)
    except Exception:
        return 0.0

# ----------------- Autocomplete helpers -----------------
async def name_autocomplete(interaction: Interaction, current: str):
    session = get_session()
    try:
        query = session.query(Score.name).distinct()
        if current:
            query = query.filter(Score.name.ilike(f"%{current}%"))
        results = query.limit(25).all()
        return [discord.app_commands.Choice(name=row[0], value=row[0]) for row in results]
    finally:
        session.close()

# ----------------- Diff string helper -----------------
def diff_values(old: float, new: float) -> str:
    diff = new - old
    sign = "+" if diff >= 0 else "-"
    return f"{old} → {new} ({sign}{abs(diff)})"

# ----------------- Safe score retrieval -----------------
def get_score(session, name: str, category: str):
    return session.query(Score).filter(Score.name == name, Score.category == category).first()

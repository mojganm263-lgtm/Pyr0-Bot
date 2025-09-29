# ---------- FILE: config.py ----------
import os

# ---------- Environment Variables ----------
TOKEN = os.getenv("TOKEN")  # Discord bot token
HF_KEY = os.getenv("HF_KEY")  # Optional Hugging Face API key

# ---------- Hugging Face Models ----------
HF_MODELS = {
    ("en", "uk"): "Helsinki-NLP/opus-mt-en-uk",
    ("uk", "en"): "Helsinki-NLP/opus-mt-uk-en",
    ("ko", "en"): "Helsinki-NLP/opus-mt-ko-en",
    ("en", "ko"): "Helsinki-NLP/opus-mt-en-ko"
}

# ---------- Default Language Pair ----------
DEFAULT_LANG_PAIR = ("en", "pt")  # English ↔ Portuguese
DEFAULT_FLAGS = ["🇺🇸", "🇵🇹"]

# ---------- FILE: cogs/translation.py ----------
import json
import requests
from discord.ext import commands
from discord import app_commands
from langdetect import detect, LangDetectException
from googletrans import Translator
from database import SessionLocal, Channel
from config import HF_MODELS, HF_KEY, DEFAULT_LANG_PAIR, DEFAULT_FLAGS

HF_HEADERS = {"Authorization": f"Bearer {HF_KEY}"} if HF_KEY else {}
translator = Translator()

class TranslationCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # ---------- Helper Functions ----------
    def translate_text(self, text: str, src: str, tgt: str) -> str:
        # Try Hugging Face first
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

        # Fallback to Google Translate
        try:
            translated = translator.translate(text, src=src, dest=tgt)
            return translated.text
        except Exception as e:
            return f"Google Translate failed: {e}"

    # ---------- Admin Check ----------
    async def is_admin(self, interaction):
        return interaction.user.guild_permissions.administrator

    # ---------- Commands ----------
    @app_commands.command(name="setchannel", description="Set this channel as translator (Admin only)")
    async def setchannel(self, interaction):
        if not await self.is_admin(interaction):
            await interaction.response.send_message("❌ Admins only.", ephemeral=True)
            return

        session = SessionLocal()
        try:
            cid = str(interaction.channel.id)
            existing = session.query(Channel).filter_by(channel_id=cid).first()
            if existing:
                await interaction.response.send_message("⚠️ Channel already configured.", ephemeral=True)
                return

            channel_obj = Channel(
                channel_id=cid,
                lang1=DEFAULT_LANG_PAIR[0],
                lang2=DEFAULT_LANG_PAIR[1],
                flags=json.dumps(DEFAULT_FLAGS)
            )
            session.add(channel_obj)
            session.commit()
            await interaction.response.send_message(
                f"✅ Channel set as translator: {DEFAULT_LANG_PAIR[0]} ↔ {DEFAULT_LANG_PAIR[1]}",
                ephemeral=True
            )
        finally:
            session.close()

    @app_commands.command(name="removechannel", description="Remove channel from translator (Admin only)")
    async def removechannel(self, interaction):
        if not await self.is_admin(interaction):
            await interaction.response.send_message("❌ Admins only.", ephemeral=True)
            return

        session = SessionLocal()
        try:
            cid = str(interaction.channel.id)
            channel_obj = session.query(Channel).filter_by(channel_id=cid).first()
            if not channel_obj:
                await interaction.response.send_message("⚠️ Channel not configured.", ephemeral=True)
                return
            session.delete(channel_obj)
            session.commit()
            await interaction.response.send_message("✅ Channel removed from translator mode.", ephemeral=True)
        finally:
            session.close()

    @app_commands.command(name="listchannels", description="List all configured translator channels")
    async def listchannels(self, interaction):
        session = SessionLocal()
        try:
            channels = session.query(Channel).all()
            if not channels:
                await interaction.response.send_message("⚠️ No channels configured.", ephemeral=True)
                return
            msg = "📚 **Translator Channels:**\n"
            for ch in channels:
                msg += f"- <#{ch.channel_id}>: {ch.lang1} ↔ {ch.lang2}\n"
            await interaction.response.send_message(msg)
        finally:
            session.close()

    # ---------- Events ----------
    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return

        session = SessionLocal()
        try:
            cid = str(message.channel.id)
            channel_obj = session.query(Channel).filter_by(channel_id=cid).first()
            if not channel_obj:
                return

            text = message.content.strip()
            if not text:
                return

            lang1 = channel_obj.lang1
            lang2 = channel_obj.lang2

            # Detect language safely
            try:
                detected = detect(text)
                if detected not in (lang1, lang2):
                    detected = lang1
            except LangDetectException:
                detected = lang1

            src, tgt = (lang1, lang2) if detected == lang1 else (lang2, lang1)
            translated = self.translate_text(text, src, tgt)

            try:
                await message.reply(f"🌐 Translation ({src} → {tgt}):\n{translated}")
            except discord.Forbidden:
                pass
        finally:
            session.close()

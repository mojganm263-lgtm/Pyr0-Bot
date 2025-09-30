# ---------- FILE: cogs/translation.py ----------
import json
import requests
from discord.ext import commands
from discord import app_commands
from langdetect import detect, LangDetectException
from googletrans import Translator
from database import SessionLocal, Channel
from config import HF_MODELS, HF_KEY, DEFAULT_FLAGS

import discord

HF_HEADERS = {"Authorization": f"Bearer {HF_KEY}"} if HF_KEY else {}
translator = Translator()

class TranslationCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # ---------- Helper ----------
    def translate_text(self, text: str, src: str, tgt: str) -> str:
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

    # ---------- Admin Check ----------
    async def is_admin(self, interaction):
        return interaction.user.guild_permissions.administrator

    # ---------- Commands ----------
    @app_commands.command(name="setchannel", description="Set this channel as translator with chosen languages (Admin only)")
    @app_commands.choices(lang1=[
        app_commands.Choice(name="English", value="en"),
        app_commands.Choice(name="Portuguese", value="pt"),
        app_commands.Choice(name="Ukrainian", value="uk"),
        app_commands.Choice(name="Korean", value="ko")
    ])
    @app_commands.choices(lang2=[
        app_commands.Choice(name="English", value="en"),
        app_commands.Choice(name="Portuguese", value="pt"),
        app_commands.Choice(name="Ukrainian", value="uk"),
        app_commands.Choice(name="Korean", value="ko")
    ])
    async def setchannel(self, interaction, lang1: app_commands.Choice[str], lang2: app_commands.Choice[str]):
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
            flags = []
            for lang in (lang1.value, lang2.value):
                if lang == "en": flags.append("🇺🇸")
                elif lang == "pt": flags.append("🇵🇹")
                elif lang == "uk": flags.append("🇺🇦")
                elif lang == "ko": flags.append("🇰🇷")
            channel_obj = Channel(
                channel_id=cid,
                lang1=lang1.value,
                lang2=lang2.value,
                flags=json.dumps(flags)
            )
            session.add(channel_obj)
            session.commit()
            await interaction.response.send_message(f"✅ Channel set as translator: {lang1.value} ↔ {lang2.value}", ephemeral=True)
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
            ch = session.query(Channel).filter_by(channel_id=cid).first()
            if not ch:
                await interaction.response.send_message("⚠️ Channel not configured.", ephemeral=True)
                return
            session.delete(ch)
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
            table = "Channel | Lang1 | Lang2 | Flags\n"
            table += "\n".join([f"<#{ch.channel_id}> | {ch.lang1} | {ch.lang2} | {', '.join(json.loads(ch.flags))}" for ch in channels])
            embed = discord.Embed(title="Translator Channels", description=f"```{table}```", color=0x00ff00)
            await interaction.response.send_message(embed=embed)
        finally:
            session.close()

    # ---------- Event ----------
    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return
        session = SessionLocal()
        try:
            cid = str(message.channel.id)
            ch = session.query(Channel).filter_by(channel_id=cid).first()
            if not ch: return
            text = message.content.strip()
            if not text: return
            try:
                detected = detect(text)
                if detected not in (ch.lang1, ch.lang2):
                    detected = ch.lang1
            except:
                detected = ch.lang1
            src, tgt = (ch.lang1, ch.lang2) if detected == ch.lang1 else (ch.lang2, ch.lang1)
            translated = self.translate_text(text, src, tgt)
            try:
                await message.reply(f"🌐 Translation ({src} → {tgt}):\n{translated}")
            except discord.Forbidden:
                pass
        finally:
            session.close()

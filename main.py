# ---------- PART 1: Imports, Environment, Flask, Database, Discord Setup ----------

import os
import threading
import requests
import time
from flask import Flask
import discord
from discord.ext import commands
from discord import app_commands
from langdetect import detect, LangDetectException
from googletrans import Translator
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from io import BytesIO
import pandas as pd

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

# ---------- Database Setup ----------
from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

Base = declarative_base()
engine = create_engine('sqlite:///scores.db', echo=False, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine)
session = SessionLocal()

# Database Models
class Score(Base):
    __tablename__ = "scores"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    category = Column(String, index=True)
    value = Column(Integer)

class History(Base):
    __tablename__ = "history"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    category = Column(String, index=True)
    value = Column(Integer)
    timestamp = Column(Integer)

Base.metadata.create_all(bind=engine)

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
translator = Translator()
# ---------- PART 2: Translation Functions and Admin Check ----------

def translate(text: str, src: str, tgt: str) -> str:
    """
    Translate text using Hugging Face models if available, fallback to Google Translate otherwise.
    """
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


def is_admin(interaction: discord.Interaction) -> bool:
    """Check if the user has admin permissions in the guild."""
    return interaction.user.guild_permissions.administrator
    # ---------- PART 3: Channel Commands ----------

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

@bot.tree.command(name="setchannel", description="Set this channel as a bidirectional translator (Admin only)")
async def setchannel(interaction: discord.Interaction):
    if not is_admin(interaction):
        await interaction.response.send_message("❌ Admins only.", ephemeral=True)
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
    await interaction.response.send_message(msg, ephemeral=False)


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
    # ---------- PART 4: Translation Events ----------

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    cid = str(message.channel.id)
    await bot.process_commands(message)

    if cid not in data["channels"]:
        return

    text = message.content.strip()
    if not text:
        return

    lang1 = data["channels"][cid]["lang1"]
    lang2 = data["channels"][cid]["lang2"]

    # Detect language safely
    try:
        detected = detect(text)
        if detected not in (lang1, lang2):
            detected = lang1
    except LangDetectException:
        detected = lang1

    src, tgt = (lang1, lang2) if detected == lang1 else (lang2, lang1)

    try:
        translated = translate(text, src, tgt)
    except Exception as e:
        translated = f"Translation error: {e}"

    try:
        await message.reply(f"🌐 Translation ({src} → {tgt}):\n{translated}")
    except discord.Forbidden:
        pass


@bot.event
async def on_reaction_add(reaction, user):
    if user.bot:
        return

    msg = reaction.message
    emoji = str(reaction.emoji)

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

    try:
        detected = detect(msg.content)
    except LangDetectException:
        detected = "en"

    src = detected

    try:
        translated = translate(msg.content, src, tgt)
    except Exception as e:
        translated = f"Translation error: {e}"

    try:
        await msg.reply(f"🌐 Translation ({src} → {tgt}):\n{translated}")
    except discord.Forbidden:
        pass
        # ---------- PART 5: Score Commands (Add, Show, Clear, Import/Export) ----------

from sqlalchemy import desc

# Helper for name autocomplete
async def name_autocomplete(interaction: discord.Interaction, current: str):
    names = session.query(Score.name).distinct().all()
    names = [n[0] for n in names if current.lower() in n[0].lower()]
    return [app_commands.Choice(name=n, value=n) for n in names[:25]]  # Discord limit

# Add or update score
@bot.tree.command(name="addscore", description="Set or update a player's absolute score (Admin only)")
@app_commands.describe(category="Choose score type", name="Player name", value="Absolute score value")
@app_commands.choices(category=[
    app_commands.Choice(name="Kill Score", value="kill"),
    app_commands.Choice(name="VS Score", value="vs")
])
@app_commands.autocomplete(name=name_autocomplete)
async def addscore(interaction, category: app_commands.Choice[str], name: str, value: str):
    if not is_admin(interaction):
        await interaction.response.send_message("❌ Admins only.", ephemeral=True)
        return
    try:
        new_val = int(str(value).replace(",", ""))
    except ValueError:
        await interaction.response.send_message("⚠️ Please provide a valid integer.", ephemeral=True)
        return

    score_entry = session.query(Score).filter_by(category=category.value, name=name).first()
    old_val = score_entry.value if score_entry else 0

    if score_entry:
        score_entry.value = new_val
    else:
        score_entry = Score(name=name, category=category.value, value=new_val)
        session.add(score_entry)

    # Record history
    history_entry = History(name=name, category=category.value, value=new_val, timestamp=int(time.time()))
    session.add(history_entry)
    session.commit()

    diff = new_val - old_val
    sign = "+" if diff >= 0 else "-"
    await interaction.response.send_message(
        f"✅ {name} updated in {category.name}: {old_val:,} → {new_val:,} ({sign}{abs(diff):,}).",
        ephemeral=True
    )


# Show score
@bot.tree.command(name="showscore", description="Show a player's score")
@app_commands.describe(category="Choose score type", name="Player name")
@app_commands.choices(category=[
    app_commands.Choice(name="Kill Score", value="kill"),
    app_commands.Choice(name="VS Score", value="vs")
])
@app_commands.autocomplete(name=name_autocomplete)
async def showscore(interaction, category: app_commands.Choice[str], name: str):
    score_entry = session.query(Score).filter_by(category=category.value, name=name).first()
    if not score_entry:
        await interaction.response.send_message(f"⚠️ {name} not found in {category.name}.", ephemeral=True)
    else:
        await interaction.response.send_message(f"📊 {name} has {score_entry.value:,} points in {category.name}.")


# Clear a name
@bot.tree.command(name="clearscore", description="Clear a player's scores (Admin only)")
@app_commands.describe(name="Player name to remove")
@app_commands.autocomplete(name=name_autocomplete)
async def clearscore(interaction, name: str):
    if not is_admin(interaction):
        await interaction.response.send_message("❌ Admins only.", ephemeral=True)
        return
    session.query(Score).filter_by(name=name).delete()
    session.query(History).filter_by(name=name).delete()
    session.commit()
    await interaction.response.send_message(f"✅ All scores for {name} have been cleared.", ephemeral=True)
    # ---------- PART 6: Score Table, Leaderboard, List Names ----------

async def send_long_message(interaction, header, lines, ephemeral=False):
    max_chars = 1800
    chunk = []
    current_len = len(header) + 2
    for line in lines:
        if current_len + len(line) + 1 > max_chars and chunk:
            msg = header + "\n" + "\n".join(chunk)
            if not hasattr(interaction, "followup_sent") or not interaction.followup_sent:
                await interaction.response.send_message(msg, ephemeral=ephemeral)
                interaction.followup_sent = True
            else:
                await interaction.followup.send(msg, ephemeral=ephemeral)
            chunk = []
            current_len = len(header) + 2
        chunk.append(line)
        current_len += len(line) + 1
    if chunk:
        msg = header + "\n" + "\n".join(chunk)
        if not hasattr(interaction, "followup_sent") or not interaction.followup_sent:
            await interaction.response.send_message(msg, ephemeral=ephemeral)
            interaction.followup_sent = True
        else:
            await interaction.followup.send(msg, ephemeral=ephemeral)


# Generate lines for table
async def generate_score_lines(category_value, show_diff=False):
    if show_diff:
        # Compute last diff per name
        diffs = {}
        last_vals = {}
        history_entries = session.query(History).filter_by(category=category_value).order_by(History.timestamp).all()
        for h in history_entries:
            diff = h.value - last_vals.get(h.name, 0)
            diffs[h.name] = diffs.get(h.name, 0) + diff
            last_vals[h.name] = h.value
        data_to_show = diffs
    else:
        scores_query = session.query(Score).filter_by(category=category_value).all()
        data_to_show = {s.name: s.value for s in scores_query}

    sorted_scores = sorted(data_to_show.items(), key=lambda x: x[1], reverse=True)
    lines = []
    for i, (name, val) in enumerate(sorted_scores, start=1):
        if show_diff:
            lines.append(f"{i:<4}  {name:<20}  {val:,}")
        else:
            lines.append(f"{i:<4}  {name:<20}  {val:,} 🔥")
    return lines


# Score Table Command
@bot.tree.command(name="scoretable", description="Show scores as a formatted text table")
@app_commands.choices(category=[
    app_commands.Choice(name="Kill Score", value="kill"),
    app_commands.Choice(name="VS Score", value="vs")
])
@app_commands.choices(diff=[
    app_commands.Choice(name="Yes", value="yes"),
    app_commands.Choice(name="No", value="no")
])
async def scoretable(interaction, category: app_commands.Choice[str], diff: app_commands.Choice[str] = None):
    show_diff = diff and diff.value == "yes"
    lines = await generate_score_lines(category.value, show_diff=show_diff)
    if not lines:
        await interaction.response.send_message(f"⚠️ No scores for {category.name}.", ephemeral=True)
        return
    await send_long_message(interaction, f"📊 **{category.name} Table**", lines)


# Leaderboard Command
@bot.tree.command(name="leaderboard", description="Show Kill Score leaderboard")
async def leaderboard(interaction):
    scores_query = session.query(Score).filter_by(category="kill").order_by(desc(Score.value)).all()
    if not scores_query:
        await interaction.response.send_message("⚠️ No kill scores available.", ephemeral=True)
        return
    lines = [f"{i}. {s.name} — {s.value:,} 🔥" for i, s in enumerate(scores_query, start=1)]
    await send_long_message(interaction, "🏆 **Kill Score Leaderboard** 🏆", lines)


# List Names Command
@bot.tree.command(name="listnames", description="List all names in a score category")
@app_commands.choices(category=[
    app_commands.Choice(name="Kill Score", value="kill"),
    app_commands.Choice(name="VS Score", value="vs")
])
async def listnames(interaction, category: app_commands.Choice[str]):
    names_query = session.query(Score.name).filter_by(category=category.value).distinct().all()
    names = [n[0] for n in names_query]
    if not names:
        await interaction.response.send_message(f"⚠️ No names in {category.name}.", ephemeral=True)
        return
    await send_long_message(interaction, f"📋 **Names in {category.name}:**", names, ephemeral=True)
    # ---------- PART 7: Graph Commands (Line & Pie Charts) ----------

import pandas as pd
from io import BytesIO

# Line Chart of Score Progression
@bot.tree.command(name="scoreline", description="Show score progression as a line chart")
@app_commands.choices(category=[
    app_commands.Choice(name="Kill Score", value="kill"),
    app_commands.Choice(name="VS Score", value="vs")
])
async def scoreline(interaction, category: app_commands.Choice[str]):
    history_entries = session.query(History).filter_by(category=category.value).order_by(History.timestamp).all()
    if not history_entries:
        await interaction.response.send_message(f"⚠️ No history for {category.name}.", ephemeral=True)
        return

    df = pd.DataFrame([{
        "name": h.name,
        "timestamp": pd.to_datetime(h.timestamp, unit='s'),
        "value": h.value
    } for h in history_entries])

    top_names = df.groupby("name")["value"].max().sort_values(ascending=False).head(20).index.tolist()
    df = df[df["name"].isin(top_names)]
    df = df.pivot(index="timestamp", columns="name", values="value").fillna(method='ffill').fillna(0)

    fig, ax = plt.subplots(figsize=(max(8, len(top_names)*0.5), 6))
    df.plot(ax=ax, marker="o")
    ax.set_title(f"{category.name} Progression")
    ax.set_xlabel("Time")
    ax.set_ylabel("Score")
    ax.legend(loc='upper left', fontsize=8)
    ax.get_yaxis().set_major_formatter(matplotlib.ticker.FuncFormatter(lambda x, p: format(int(x), ',')))
    plt.xticks(rotation=45, ha='right')
    plt.tight_layout()

    buf = BytesIO()
    plt.savefig(buf, format="png")
    buf.seek(0)
    await interaction.response.send_message(file=discord.File(buf, filename="linechart.png"))


# Pie Chart of Score Distribution
@bot.tree.command(name="scorepie", description="Show score distribution as a pie chart")
@app_commands.choices(category=[
    app_commands.Choice(name="Kill Score", value="kill"),
    app_commands.Choice(name="VS Score", value="vs")
])
async def scorepie(interaction, category: app_commands.Choice[str]):
    scores_query = session.query(Score).filter_by(category=category.value).all()
    if not scores_query:
        await interaction.response.send_message(f"⚠️ No data for {category.name}.", ephemeral=True)
        return

    df = pd.DataFrame([{"name": s.name, "value": s.value} for s in scores_query])
    df = df.sort_values("value", ascending=False)
    top_n = 10
    top_scores = df.head(top_n)
    others = df.iloc[top_n:]

    labels = top_scores["name"].tolist()
    values = top_scores["value"].tolist()
    if not others.empty:
        labels.append("Other")
        values.append(others["value"].sum())

    fig, ax = plt.subplots(figsize=(8, 8))
    ax.pie(values, labels=labels, autopct="%1.1f%%", startangle=90)
    ax.set_title(f"{category.name} Distribution")
    plt.tight_layout()

    buf = BytesIO()
    plt.savefig(buf, format="png")
    buf.seek(0)
    await interaction.response.send_message(file=discord.File(buf, filename="piechart.png"))
    # ---------- PART 8: /allcommands and Bot Startup & Flask Integration ----------

@bot.tree.command(name="allcommands", description="List all slash commands added by this bot")
async def allcommands(interaction: discord.Interaction):
    registry = [
        ("setchannel", "Set this channel as a bidirectional translator (Admin only)", True),
        ("removechannel", "Remove this channel from translator mode (Admin only)", True),
        ("listchannels", "List all configured translator channels", False),
        ("setlanguages", "Set language pair (Admin only)", True),
        ("addscore", "Set or update a player's absolute score (Admin only)", True),
        ("showscore", "Show a player's score", False),
        ("clearscore", "Clear a player's scores (Admin only)", True),
        ("scoretable", "Show scores as a formatted text table", False),
        ("leaderboard", "Show Kill Score leaderboard", False),
        ("listnames", "List all names in a score category", False),
        ("scoreline", "Show score progression as a line chart", False),
        ("scorepie", "Show score distribution as a pie chart", False),
        ("allcommands", "List all slash commands added by this bot", False)
    ]

    lines = []
    for name, desc, admin in registry:
        adm = " (Admin)" if admin else ""
        lines.append(f"/{name}{adm} — {desc}")

    await send_long_message(interaction, "🤖 **Available Slash Commands**", lines, ephemeral=True)


@bot.event
async def on_ready():
    try:
        synced = await bot.tree.sync()
        print(f"✅ Synced {len(synced)} commands")
    except Exception as e:
        print(f"❌ Sync failed: {e}")
    print(f"🤖 Logged in as {bot.user}")


if __name__ == "__main__":
    # Start Flask in a separate thread
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()

    # Start the Discord bot
    try:
        bot.run(TOKEN)
    except Exception as e:
        print("❌ Bot failed to start:", e)
        raise

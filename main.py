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

matplotlib.use("Agg")  # Headless backend

import matplotlib.pyplot as plt

from io import BytesIO


# ---------- Environment Variables ----------

TOKEN = os.getenv("TOKEN")

HF_KEY = os.getenv("HF_KEY")  # Optional


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

@bot.tree.command(name="setchannel", description="Set this channel as a bidirectional translator (Admin only)")

async def setchannel(interaction: discord.Interaction):

    if not is_admin(interaction):

        await interaction.response.send_message("❌ Admins only.", ephemeral=True)

        return


    cid = str(interaction.channel.id)

    if cid in data["channels"]:

        await interaction.response.send_message("⚠️ Channel already configured.", ephemeral=True)

        return


    # Default language pair: English ↔ Portuguese

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


    # Always allow commands to process

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


    # Determine translation direction

    src, tgt = (lang1, lang2) if detected == lang1 else (lang2, lang1)


    # Translate using HF first, then fallback

    try:

        translated = translate(text, src, tgt)

    except Exception as e:

        translated = f"Translation error: {e}"


    # Reply with translation

    try:

        await message.reply(f"🌐 Translation ({src} → {tgt}):\n{translated}")

    except discord.Forbidden:

        pass  # silently ignore if cannot reply



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


    # Detect source language safely

    try:

        detected = detect(msg.content)

    except LangDetectException:

        detected = "en"


    src = detected


    try:

        translated = translate(msg.content, src, tgt)

    except Exception as e:

        translated = f"Translation error: {e}"


    # Reply with translation

    try:

        await msg.reply(f"🌐 Translation ({src} → {tgt}):\n{translated}")

    except discord.Forbidden:

        pass
        # ---------- PART 5: Scoring Commands (Add/Show/Export/Import/Clear) ----------

@bot.tree.command(name="addscore", description="Add to a player's score")
@app_commands.describe(category="Choose score type", name="Player name", value="Points to add")
@app_commands.choices(category=[
    app_commands.Choice(name="Kill Score", value="kill"),
    app_commands.Choice(name="VS Score", value="vs")
])
async def addscore(interaction, category: app_commands.Choice[str], name: str, value: int):
    scores[category.value][name] = scores[category.value].get(name, 0) + value
    scores["history"].append({
        "category": category.value,
        "name": name,
        "value": scores[category.value][name],
        "timestamp": interaction.created_at.timestamp()
    })
    save_data(data)
    await interaction.response.send_message(
        f"✅ Added {value} points to **{name}** in {category.name}. "
        f"New total: {scores[category.value][name]:,}"
    )


@bot.tree.command(name="showscore", description="Show a player's score")
@app_commands.describe(category="Choose score type", name="Player name")
@app_commands.choices(category=[
    app_commands.Choice(name="Kill Score", value="kill"),
    app_commands.Choice(name="VS Score", value="vs")
])
async def showscore(interaction, category: app_commands.Choice[str], name: str):
    val = scores[category.value].get(name)
    if val is None:
        await interaction.response.send_message(f"⚠️ {name} not found in {category.name}.", ephemeral=True)
    else:
        await interaction.response.send_message(f"📊 {name} has {val:,} points in {category.name}.")


@bot.tree.command(name="exportcsv", description="Export scores to CSV file")
async def exportcsv(interaction):
    filename = "scores.csv"
    with open(filename, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Category", "Name", "Score"])
        for cat, entries in scores.items():
            if cat == "history":
                continue
            for name, val in entries.items():
                writer.writerow([cat, name, val])

    await interaction.response.send_message(file=discord.File(filename))


@bot.tree.command(name="importcsv", description="Import scores from uploaded CSV file (Admin only)")
async def importcsv(interaction, attachment: discord.Attachment):
    if not is_admin(interaction):
        await interaction.response.send_message("❌ Admins only.", ephemeral=True)
        return

    if not attachment.filename.endswith(".csv"):
        await interaction.response.send_message("⚠️ Please upload a CSV file.", ephemeral=True)
        return

    content = await attachment.read()
    decoded = content.decode("utf-8").splitlines()
    reader = csv.DictReader(decoded)

    for row in reader:
        cat = row["Category"]
        name = row["Name"]
        val = int(row["Score"])
        scores.setdefault(cat, {})[name] = val

    save_data(data)
    await interaction.response.send_message("✅ Scores imported from CSV.")


@bot.tree.command(name="clearscores", description="Clear all scores (Admin only)")
async def clearscores(interaction):
    if not is_admin(interaction):
        await interaction.response.send_message("❌ Admins only.", ephemeral=True)
        return

    scores["kill"].clear()
    scores["vs"].clear()
    scores["history"].clear()
    save_data(data)
    await interaction.response.send_message("✅ All scores cleared.")
    # ---------- PART 6: Helper Functions for Display ----------

async def send_long_message(interaction, header, lines, ephemeral=False):
    """
    Send a long message in chunks to avoid Discord 2000-char limit.
    - header: string to appear at the top of each chunk
    - lines: list of strings (each line is one name/score entry)
    - ephemeral: whether message should be visible only to the user
    """
    chunk_size = 20  # number of lines per message
    for i in range(0, len(lines), chunk_size):
        chunk = lines[i:i + chunk_size]
        msg = header + "\n" + "\n".join(chunk)
        if i == 0:
            await interaction.response.send_message(msg, ephemeral=ephemeral)
        else:
            await interaction.followup.send(msg, ephemeral=ephemeral)


def compute_diff(category_value):
    """
    Compute the difference between the current score and the previous score
    for each name in the given category.
    Returns a dict: {name: diff_value}
    """
    diff_data = {}
    last_values = {}
    for entry in scores.get("history", []):
        if entry["category"] == category_value:
            diff_data[entry["name"]] = entry["value"] - last_values.get(entry["name"], 0)
            last_values[entry["name"]] = entry["value"]
    return diff_data


async def generate_score_lines(category_value, show_diff=False):
    """
    Generate formatted lines for table display.
    - category_value: 'kill' or 'vs'
    - show_diff: if True, show difference instead of raw score
    """
    if show_diff:
        data_to_show = compute_diff(category_value)
    else:
        data_to_show = scores.get(category_value, {})

    sorted_scores = sorted(data_to_show.items(), key=lambda x: x[1], reverse=True)
    lines = []
    for i, (name, val) in enumerate(sorted_scores, start=1):
        suffix = "" if show_diff else "🔥"  # emoji only for raw score
        lines.append(f"{i:<4}  {name:<14}  {val:,}{suffix}")
    return lines
    # ---------- PART 7: Table / Leaderboard / List Display Commands ----------

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


@bot.tree.command(name="leaderboard", description="Show Kill Score leaderboard")
async def leaderboard(interaction):
    kill_scores = scores.get("kill", {})
    if not kill_scores:
        await interaction.response.send_message("⚠️ No kill scores available.", ephemeral=True)
        return

    sorted_scores = sorted(kill_scores.items(), key=lambda x: x[1], reverse=True)
    lines = [f"{i}. {name} — {val:,}🔥" for i, (name, val) in enumerate(sorted_scores, start=1)]
    await send_long_message(interaction, "🏆 **Kill Score Leaderboard** 🏆", lines)


@bot.tree.command(name="listnames", description="List all names in a score category")
@app_commands.choices(category=[
    app_commands.Choice(name="Kill Score", value="kill"),
    app_commands.Choice(name="VS Score", value="vs")
])
async def listnames(interaction, category: app_commands.Choice[str]):
    data_scores = scores.get(category.value, {})
    if not data_scores:
        await interaction.response.send_message(f"⚠️ No names in {category.name}.", ephemeral=True)
        return

    lines = list(data_scores.keys())
    await send_long_message(interaction, f"📋 **Names in {category.name}:**", lines, ephemeral=True)
    # ---------- PART 8: Graph Commands (Line & Pie Charts) ----------

@bot.tree.command(name="scoreline", description="Show score progression as a line chart")
@app_commands.choices(category=[
    app_commands.Choice(name="Kill Score", value="kill"),
    app_commands.Choice(name="VS Score", value="vs")
])
async def scoreline(interaction, category: app_commands.Choice[str]):
    history = [h for h in scores.get("history", []) if h["category"] == category.value]
    if not history:
        await interaction.response.send_message(f"⚠️ No history for {category.name}.", ephemeral=True)
        return

    import datetime
    series = {}
    for h in history:
        t = datetime.datetime.fromtimestamp(h["timestamp"])
        series.setdefault(h["name"], []).append((t, h["value"]))

    # Limit legend to top 20 names
    sorted_names = sorted(series.keys())[:20]
    fig, ax = plt.subplots(figsize=(max(8, len(sorted_names)*0.5), 6))

    for name in sorted_names:
        points = series[name]
        points.sort(key=lambda x: x[0])
        times, vals = zip(*points)
        ax.plot(times, vals, marker="o", label=name)

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


@bot.tree.command(name="scorepie", description="Show score distribution as a pie chart")
@app_commands.choices(category=[
    app_commands.Choice(name="Kill Score", value="kill"),
    app_commands.Choice(name="VS Score", value="vs")
])
async def scorepie(interaction, category: app_commands.Choice[str]):
    data_scores = scores.get(category.value, {})
    if not data_scores:
        await interaction.response.send_message(f"⚠️ No data for {category.name}.", ephemeral=True)
        return

    # Top 10 names; rest grouped as "Other"
    sorted_scores = sorted(data_scores.items(), key=lambda x: x[1], reverse=True)
    top_n = 10
    top_scores = sorted_scores[:top_n]
    others = sorted_scores[top_n:]

    labels = [name for name, _ in top_scores]
    values = [val for _, val in top_scores]

    if others:
        labels.append("Other")
        values.append(sum(val for _, val in others))

    fig, ax = plt.subplots(figsize=(8, 8))
    ax.pie(values, labels=labels, autopct="%1.1f%%", startangle=90)
    ax.set_title(f"{category.name} Distribution")
    plt.tight_layout()

    buf = BytesIO()
    plt.savefig(buf, format="png")
    buf.seek(0)
    await interaction.response.send_message(file=discord.File(buf, filename="piechart.png"))
    # ---------- PART 9: Bot Startup & Flask Integration ----------

@bot.event
async def on_ready():
    try:
        synced = await bot.tree.sync()
        print(f"✅ Synced {len(synced)} commands")
    except Exception as e:
        print(f"❌ Sync failed: {e}")
    print(f"🤖 Logged in as {bot.user}")


if __name__ == "__main__":
    # Start Flask in a separate thread so the bot stays alive on Render
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()

    # Start the Discord bot
    bot.run(TOKEN)

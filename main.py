# ---------- Part 1: Imports, Env, Flask, JSON ----------
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
matplotlib.use('Agg')  # Headless mode for servers
import matplotlib.pyplot as plt
from io import BytesIO

# ---------- Environment Variables ----------
TOKEN = os.getenv("TOKEN")
HF_KEY = os.getenv("HF_KEY")  # Optional for Hugging Face rate-limited models

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
        return {"channels": {}, "scores": {"kill_score": {}, "vs_score": {}}}
    except json.JSONDecodeError:
        return {"channels": {}, "scores": {"kill_score": {}, "vs_score": {}}}

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)

data = load_data()

# Scores JSON
SCORE_FILE = "scores.json"

def load_scores():
    try:
        with open(SCORE_FILE, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return {"kill": {}, "vs": {}, "history": []}
    except json.JSONDecodeError:
        return {"kill": {}, "vs": {}, "history": []}

def save_scores(scores):
    with open(SCORE_FILE, "w") as f:
        json.dump(scores, f, indent=4)

scores = load_scores()
# ---------- Part 2: Translation Setup ----------
# Hugging Face working models
HF_MODELS = {
    ("en", "uk"): "Helsinki-NLP/opus-mt-en-uk",
    ("uk", "en"): "Helsinki-NLP/opus-mt-uk-en",
    ("ko", "en"): "Helsinki-NLP/opus-mt-ko-en",
}

HF_HEADERS = {"Authorization": f"Bearer {HF_KEY}"} if HF_KEY else {}

# Google Translator fallback
translator = Translator()

def translate(text: str, src_lang: str, tgt_lang: str) -> str:
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
            return "HF Translation failed."
        except requests.exceptions.RequestException as e:
            return f"HF request failed: {e}"

    # Fallback to Google Translate
    try:
        translated = translator.translate(text, src=src_lang, dest=tgt_lang)
        return translated.text
    except Exception as e:
        return f"Google Translate failed: {e}"
        # ---------- Part 3: Discord Bot Setup ----------
intents = discord.Intents.default()
intents.messages = True
intents.message_content = True
intents.reactions = True

bot = commands.Bot(command_prefix="!", intents=intents)

# ---------- Admin Check ----------
def is_admin(interaction):
    return interaction.user.guild_permissions.administrator
    # ---------- Part 4: Slash Commands for Channel Management ----------
@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} commands")
    except Exception as e:
        print(f"Error syncing commands: {e}")

@bot.tree.command(name="setchannel", description="Set this channel as a translator (Admin only)")
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
    # ---------- Part 5: Bidirectional Translation & Flag Reactions ----------
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
    # ---------- Part 6: Score Tracking & Reports ----------
# Show all commands (everyone)
@bot.tree.command(name="allcommands", description="Show all slash commands")
async def allcommands(interaction: discord.Interaction):
    commands_list = [cmd.name for cmd in bot.tree.walk_commands()]
    await interaction.response.send_message(f"📜 **All Commands:**\n- " + "\n- ".join(commands_list), ephemeral=True)

# Add or update a score (Admin only)
@bot.tree.command(name="addscore", description="Add or update a score for a name (Admin only)")
@app_commands.describe(category="Choose score type", name="Name to track", value="Value to add/update")
@app_commands.choices(category=[
    app_commands.Choice(name="Kill Score", value="kill"),
    app_commands.Choice(name="VS Score", value="vs")
])
async def addscore(interaction: discord.Interaction, category: app_commands.Choice[str], name: str, value: int):
    if not is_admin(interaction):
        await interaction.response.send_message("❌ Admins only.", ephemeral=True)
        return

    scores[category.value][name] = value
    scores["history"].append({"timestamp": int(interaction.created_at.timestamp()), "category": category.value, "name": name, "value": value})
    save_scores(scores)
    await interaction.response.send_message(f"✅ {category.name} updated: {name} = {value}", ephemeral=True)

# Show table or graph with optional difference
@bot.tree.command(name="showscores", description="Show scores as table or graph")
@app_commands.describe(category="Choose score type", mode="Display as table or graph", diff="Show difference (optional)")
@app_commands.choices(category=[
    app_commands.Choice(name="Kill Score", value="kill"),
    app_commands.Choice(name="VS Score", value="vs")
])
@app_commands.choices(mode=[
    app_commands.Choice(name="Table", value="table"),
    app_commands.Choice(name="Graph", value="graph")
])
@app_commands.choices(diff=[
    app_commands.Choice(name="Yes", value="yes"),
    app_commands.Choice(name="No", value="no")
])
async def showscores(interaction: discord.Interaction, category: app_commands.Choice[str], mode: app_commands.Choice[str], diff: app_commands.Choice[str] = None):
    data = scores.get(category.value, {})
    if not data:
        await interaction.response.send_message("⚠️ No data for this category.", ephemeral=True)
        return

    # Compute differences
    if diff and diff.value == "yes":
        diff_data = {}
        last_values = {}
        for entry in scores["history"]:
            if entry["category"] == category.value:
                diff_data[entry["name"]] = entry["value"] - last_values.get(entry["name"], 0)
                last_values[entry["name"]] = entry["value"]
        data_to_show = diff_data
    else:
        data_to_show = data

    if mode.value == "table":
        msg = f"📊 **{category.name} Table**\n"
        for name, val in data_to_show.items():
            msg += f"- {name}: {val}\n"
        await interaction.response.send_message(msg)
    else:
        # Graph output
        fig, ax = plt.subplots()
        ax.bar(data_to_show.keys(), data_to_show.values(), color='skyblue')
        ax.set_ylabel("Score")
        ax.set_title(f"{category.name}")
        buf = BytesIO()
        plt.savefig(buf, format='png')
        buf.seek(0)
        await interaction.response.send_message(file=discord.File(buf, filename="graph.png"))

# Export scores to CSV
@bot.tree.command(name="exportcsv", description="Export scores to CSV")
@app_commands.describe(category="Choose score type to export")
@app_commands.choices(category=[
    app_commands.Choice(name="Kill Score", value="kill"),
    app_commands.Choice(name="VS Score", value="vs")
])
async def exportcsv(interaction: discord.Interaction, category: app_commands.Choice[str]):
    data = scores.get(category.value, {})
    if not data:
        await interaction.response.send_message("⚠️ No data for this category.", ephemeral=True)
        return

    filename = f"{category.value}_scores.csv"
    with open(filename, "w", newline="") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(["Name", "Score"])
        for name, val in data.items():
            writer.writerow([name, val])

    await interaction.response.send_message(file=discord.File(filename))

# Import scores from CSV (Admin only)
@bot.tree.command(name="importcsv", description="Import scores from a CSV file (Admin only)")
async def importcsv(interaction: discord.Interaction, category: str, attachment: discord.Attachment):
    if not is_admin(interaction):
        await interaction.response.send_message("❌ Admins only.", ephemeral=True)
        return

    if not attachment.filename.endswith(".csv"):
        await interaction.response.send_message("⚠️ Please upload a valid CSV file.", ephemeral=True)
        return

    file_bytes = await attachment.read()
    lines = file_bytes.decode("utf-8").splitlines()
    reader = csv.reader(lines)
    next(reader, None)  # Skip header
    for row in reader:
        if len(row) == 2:
            name, val = row
            scores[category][name] = int(val)

    save_scores(scores)
    await interaction.response.send_message(f"✅ Imported scores into {category}.", ephemeral=True)
    # ---------- Part 7: Clear Commands (Admin Only) ----------
@bot.tree.command(name="clearname", description="Remove a name and its score (Admin only)")
@app_commands.describe(category="Choose score type", name="Name to remove")
@app_commands.choices(category=[
    app_commands.Choice(name="Kill Score", value="kill"),
    app_commands.Choice(name="VS Score", value="vs")
])
async def clearname(interaction: discord.Interaction, category: app_commands.Choice[str], name: str):
    if not is_admin(interaction):
        await interaction.response.send_message("❌ Admins only.", ephemeral=True)
        return
    if name in scores[category.value]:
        scores[category.value].pop(name)
        save_scores(scores)
        await interaction.response.send_message(f"✅ Removed {name} from {category.name}.", ephemeral=True)
    else:
        await interaction.response.send_message(f"⚠️ {name} not found in {category.name}.", ephemeral=True)

@bot.tree.command(name="clearscore", description="Set a score to 0 for a name (Admin only)")
@app_commands.describe(category="Choose score type", name="Name to reset")
@app_commands.choices(category=[
    app_commands.Choice(name="Kill Score", value="kill"),
    app_commands.Choice(name="VS Score", value="vs")
])
async def clearscore(interaction: discord.Interaction, category: app_commands.Choice[str], name: str):
    if not is_admin(interaction):
        await interaction.response.send_message("❌ Admins only.", ephemeral=True)
        return
    if name in scores[category.value]:
        scores[category.value][name] = 0
        save_scores(scores)
        await interaction.response.send_message(f"✅ Reset {category.name} score for {name} to 0.", ephemeral=True)
    else:
        await interaction.response.send_message(f"⚠️ {name} not found in {category.name}.", ephemeral=True)

@bot.tree.command(name="clearall", description="Clear all scores in a category (Admin only)")
@app_commands.describe(category="Choose score type to clear")
@app_commands.choices(category=[
    app_commands.Choice(name="Kill Score", value="kill"),
    app_commands.Choice(name="VS Score", value="vs")
])
async def clearall(interaction: discord.Interaction, category: app_commands.Choice[str]):
    if not is_admin(interaction):
        await interaction.response.send_message("❌ Admins only.", ephemeral=True)
        return
    scores[category.value] = {}
    save_scores(scores)
    await interaction.response.send_message(f"✅ All {category.name} scores cleared.", ephemeral=True)

# ---------- Run Flask + Bot ----------
if __name__ == "__main__":
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.start()
    bot.run(TOKEN)

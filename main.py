# --- PART 1: Imports, setup, and JSON helpers ---

import discord
from discord import app_commands
from discord.ext import commands
import json
import os
import matplotlib
matplotlib.use("Agg")  # Headless backend for Render
import matplotlib.pyplot as plt
import io
from googletrans import Translator
from transformers import pipeline
import asyncio

intents = discord.Intents.default()
intents.message_content = True
intents.reactions = True

bot = commands.Bot(command_prefix="!", intents=intents)

# Load JSON
SETTINGS_FILE = "data.json"
if os.path.exists(SETTINGS_FILE):
    with open(SETTINGS_FILE, "r") as f:
        settings = json.load(f)
else:
    settings = {"channels": {}, "scores": {"kill": {}, "vs": {}}}

scores = settings["scores"]

def save_settings():
    with open(SETTINGS_FILE, "w") as f:
        json.dump(settings, f, indent=4)

# Translators
translator = Translator()
try:
    hf_translator = pipeline("translation", model="Helsinki-NLP/opus-mt-mul-en")
except Exception:
    hf_translator = None
    # --- PART 2: Translation logic and helpers ---

def translate_text(text: str, src: str, tgt: str) -> str:
    """
    Translate text using Hugging Face if available,
    otherwise fallback to Google Translate.
    """
    # Hugging Face first
    if hf_translator and src != tgt:
        try:
            result = hf_translator(text)
            if isinstance(result, list) and "translation_text" in result[0]:
                return result[0]["translation_text"]
        except Exception:
            pass  # fallback

    # Googletrans fallback
    try:
        translated = translator.translate(text, src=src, dest=tgt)
        return translated.text
    except Exception as e:
        return f"[Translation failed: {e}]"

# Simple admin check
def is_admin(interaction: discord.Interaction) -> bool:
    return interaction.user.guild_permissions.administrator
    # --- PART 3: Bot Events + /allcommands command ---

@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")
    try:
        synced = await bot.tree.sync()
        print(f"🔗 Synced {len(synced)} commands")
    except Exception as e:
        print(f"⚠️ Sync failed: {e}")

@bot.tree.command(name="allcommands", description="Show all available slash commands")
async def allcommands(interaction: discord.Interaction):
    commands_list = [cmd.name for cmd in bot.tree.get_commands()]
    msg = "📜 **Available Commands:**\n" + "\n".join(f"- /{c}" for c in commands_list)
    await interaction.response.send_message(msg, ephemeral=False)
    # --- PART 4: Channel setup commands ---

def is_admin(interaction):
    return interaction.user.guild_permissions.administrator

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
    # --- PART 5: Bidirectional & flag reaction translation ---

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
    # --- PART 6: Score tracking & reports ---

# Show all commands (for everyone)
@bot.tree.command(name="allcommands", description="Show all slash commands")
async def allcommands(interaction: discord.Interaction):
    commands_list = [cmd.name for cmd in bot.tree.walk_commands()]
    await interaction.response.send_message(
        f"📜 **All Commands:**\n- " + "\n- ".join(commands_list),
        ephemeral=True
    )

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
    scores["history"].append({
        "timestamp": int(interaction.created_at.timestamp()),
        "category": category.value,
        "name": name,
        "value": value
    })
    save_scores(scores)
    await interaction.response.send_message(
        f"✅ {category.name} updated: {name} = {value}",
        ephemeral=True
    )

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
        plt.savefig(buf, format="png")
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
    # --- PART 7: Clear commands (Admin only) ---

# Remove a name and its score
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

# Reset a score for a name (set to 0)
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

# Clear all scores in a category
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

# List all names in a category
@bot.tree.command(name="listnames", description="List all names in a score category")
@app_commands.describe(category="Choose score type")
@app_commands.choices(category=[
    app_commands.Choice(name="Kill Score", value="kill"),
    app_commands.Choice(name="VS Score", value="vs")
])
async def listnames(interaction: discord.Interaction, category: app_commands.Choice[str]):
    data = scores.get(category.value, {})
    if not data:
        await interaction.response.send_message("⚠️ No names in this category.", ephemeral=True)
        return

    msg = f"📋 **Names in {category.name}:**\n" + "\n".join(data.keys())
    await interaction.response.send_message(msg, ephemeral=True)
    # --- PART 8: Run Flask + Discord Bot ---

if __name__ == "__main__":
    # Start Flask in a separate thread to keep the bot alive
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.start()

    # Run the Discord bot
    bot.run(TOKEN)

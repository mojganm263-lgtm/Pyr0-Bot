import discord
from discord import app_commands
from discord.ext import commands
import json
import matplotlib.pyplot as plt
from datetime import datetime
import os
import io
from aiohttp import web
from transformers import pipeline
import asyncio

# ---------------- Bot Setup ---------------- #
intents = discord.Intents.default()
intents.message_content = True
intents.reactions = True

bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree  # For slash commands

DATA_FILE = "data.json"

# Load or initialize data
if os.path.exists(DATA_FILE):
    with open(DATA_FILE, "r") as f:
        data = json.load(f)
else:
    data = {"channels": [], "numbers": {}}

def save_data():
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)

def ensure_channel(channel_id):
    return channel_id in data["channels"]

# ---------------- Hugging Face ---------------- #
translator = pipeline("translation", model="Helsinki-NLP/opus-mt-mul-en")

def translate_text(text, target_lang):
    model_map = {
        "en": "Helsinki-NLP/opus-mt-mul-en",
        "ko": "Helsinki-NLP/opus-mt-en-ko",
        "uk": "Helsinki-NLP/opus-mt-en-uk"
    }
    model_name = model_map.get(target_lang, "Helsinki-NLP/opus-mt-mul-en")
    pipe = pipeline("translation", model=model_name)
    return pipe(text, max_length=400)[0]["translation_text"]

# ---------------- Slash Commands ---------------- #
@tree.command(name="setchannel", description="Set current channel for translations")
async def setchannel(interaction: discord.Interaction):
    ch_id = interaction.channel.id
    if ch_id not in data["channels"]:
        data["channels"].append(ch_id)
        save_data()
        await interaction.response.send_message(f"Channel {interaction.channel.name} set for translations.")
    else:
        await interaction.response.send_message("This channel is already set.")

@tree.command(name="translate", description="Translate text to a language")
@app_commands.describe(lang="Target language (en, ko, uk)", text="Text to translate")
async def translate(interaction: discord.Interaction, lang: str, text: str):
    if not ensure_channel(interaction.channel.id):
        return
    translated = translate_text(text, lang.lower())
    await interaction.response.send_message(translated)

@tree.command(name="add", description="Add a number to a name")
@app_commands.describe(name="Name to track", number="Number to add")
async def add(interaction: discord.Interaction, name: str, number: float):
    if not ensure_channel(interaction.channel.id):
        return
    if name not in data["numbers"]:
        data["numbers"][name] = []
    data["numbers"][name].append({"value": number, "timestamp": datetime.now().isoformat()})
    save_data()
    await interaction.response.send_message(f"Added {number} for {name}.")

@tree.command(name="view", description="View all numbers for a name")
@app_commands.describe(name="Name to view")
async def view(interaction: discord.Interaction, name: str):
    if not ensure_channel(interaction.channel.id):
        return
    if name not in data["numbers"]:
        await interaction.response.send_message(f"No data for {name}.")
        return
    msg = f"Data for {name}:\n"
    for entry in data["numbers"][name]:
        msg += f"{entry['timestamp']}: {entry['value']}\n"
    await interaction.response.send_message(msg)

@tree.command(name="viewall", description="View numbers for all names")
async def viewall(interaction: discord.Interaction):
    if not ensure_channel(interaction.channel.id):
        return
    if not data["numbers"]:
        await interaction.response.send_message("No numbers stored.")
        return
    msg = ""
    for name, entries in data["numbers"].items():
        msg += f"**{name}**\n"
        for entry in entries:
            msg += f"{entry['timestamp']}: {entry['value']}\n"
    await interaction.response.send_message(msg)

@tree.command(name="delete", description="Delete all data for a name")
@app_commands.describe(name="Name to delete")
async def delete(interaction: discord.Interaction, name: str):
    if not ensure_channel(interaction.channel.id):
        return
    if name in data["numbers"]:
        del data["numbers"][name]
        save_data()
        await interaction.response.send_message(f"Deleted all data for {name}.")
    else:
        await interaction.response.send_message(f"No data for {name}.")

@tree.command(name="graph", description="Generate a graph for a name")
@app_commands.describe(name="Name to graph")
async def graph(interaction: discord.Interaction, name: str):
    if not ensure_channel(interaction.channel.id):
        return
    if name not in data["numbers"]:
        await interaction.response.send_message(f"No data for {name}.")
        return
    values = [entry["value"] for entry in data["numbers"][name]]
    times = [entry["timestamp"] for entry in data["numbers"][name]]
    plt.figure()
    plt.plot(times, values, marker="o")
    plt.title(f"Graph for {name}")
    plt.xlabel("Time")
    plt.ylabel("Value")
    plt.xticks(rotation=45)
    plt.tight_layout()
    buf = io.BytesIO()
    plt.savefig(buf, format="png")
    buf.seek(0)
    plt.close()
    await interaction.response.send_message(file=discord.File(fp=buf, filename=f"{name}_graph.png"))

@tree.command(name="table", description="Generate a table for a name")
@app_commands.describe(name="Name to show table")
async def table(interaction: discord.Interaction, name: str):
    if not ensure_channel(interaction.channel.id):
        return
    if name not in data["numbers"]:
        await interaction.response.send_message(f"No data for {name}.")
        return
    msg = f"**Table for {name}**\nTime | Value\n--- | ---\n"
    for entry in data["numbers"][name]:
        msg += f"{entry['timestamp']} | {entry['value']}\n"
    await interaction.response.send_message(msg)

# ---------------- Reaction-based translation ---------------- #
LANG_FLAGS = {"🇺🇸": "en", "🇰🇷": "ko", "🇺🇦": "uk"}

@bot.event
async def on_reaction_add(reaction, user):
    if user.bot or reaction.message.channel.id not in data["channels"]:
        return
    lang = LANG_FLAGS.get(str(reaction.emoji))
    if lang:
        translated = translate_text(reaction.message.content, lang)
        await reaction.message.reply(translated)

# ---------------- Minimal Web Server ---------------- #
async def handle(request):
    return web.Response(text="Bot running!")

app = web.Application()
app.router.add_get("/", handle)

async def run_webserver():
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', int(os.environ.get("PORT", 10000)))
    await site.start()

# ---------------- Run Bot & Web Server ---------------- #
@bot.event
async def on_ready():
    await tree.sync()  # Register all slash commands
    print(f"Logged in as {bot.user}")

async def main():
    await run_webserver()
    await bot.start(os.environ.get("DISCORD_TOKEN"))

asyncio.run(main())

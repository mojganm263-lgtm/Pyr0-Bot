# -------------------
# Fix for Python 3.13 Render (skip voice/audio)
# -------------------
import sys
sys.modules['discord.opus'] = None
sys.modules['discord.player'] = None
sys.modules['discord.voice_client'] = None

# -------------------
# Imports
# -------------------
import discord
from discord.ext import commands
from discord.commands import option  # py-cord slash commands
import json
from datetime import datetime
import matplotlib.pyplot as plt
from io import BytesIO
from threading import Thread
from flask import Flask
import os

# -------------------
# Flask server for Render keep-alive
# -------------------
app = Flask(__name__)

@app.route("/")
def home():
    return "Bot is running!"

def run_flask():
    app.run(host="0.0.0.0", port=5000)

Thread(target=run_flask).start()

# -------------------
# Bot setup
# -------------------
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="/", intents=intents)

# -------------------
# Load or initialize JSON
# -------------------
DATA_FILE = "data.json"
try:
    with open(DATA_FILE, "r") as f:
        data = json.load(f)
except FileNotFoundError:
    data = {"translate_channels": {}, "entries": []}

def save_data():
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)

# -------------------
# Translation helper
# -------------------
def translate_message(text, pair):
    from transformers import pipeline
    if pair == "en-uk":
        if any("\u0400" <= c <= "\u04FF" for c in text):
            model = "Helsinki-NLP/opus-mt-uk-en"
        else:
            model = "Helsinki-NLP/opus-mt-en-uk"
    elif pair == "en-ko":
        if any("\uAC00" <= c <= "\uD7AF" for c in text):
            model = "Helsinki-NLP/opus-mt-ko-en"
        else:
            model = "Helsinki-NLP/opus-mt-en-ko"
    translator = pipeline("translation", model=model, device=-1)
    return translator(text, max_length=512)[0]['translation_text']

# -------------------
# Slash commands
# -------------------
@bot.slash_command(name="setchannel", description="Set a translation channel")
@option("channel", discord.TextChannel, description="Select the channel")
@option("language_pair", str, description="Choose language pair (en-uk or en-ko)")
async def setchannel(ctx, channel, language_pair):
    if language_pair not in ["en-uk", "en-ko"]:
        await ctx.respond("Invalid language pair! Use 'en-uk' or 'en-ko'.")
        return
    data["translate_channels"][str(channel.id)] = language_pair
    save_data()
    await ctx.respond(f"Channel {channel.mention} set to {language_pair} translation.")

@bot.slash_command(name="log", description="Log a number with a name")
@option("name", str, description="Name/label for the entry")
@option("value", int, description="Number to log")
async def log(ctx, name, value):
    entry = {"name": name, "value": value, "timestamp": datetime.utcnow().isoformat()}
    data["entries"].append(entry)
    save_data()
    await ctx.respond(f"Logged {value} for {name} at {entry['timestamp']}.")

@bot.slash_command(name="report", description="Show report for a name or all names")
@option("start", str, description="Start timestamp YYYY-MM-DDTHH:MM")
@option("end", str, description="End timestamp YYYY-MM-DDTHH:MM")
@option("name", str, description="Name to filter or 'all' for all names")
async def report(ctx, start, end, name):
    try:
        start_dt = datetime.fromisoformat(start)
        end_dt = datetime.fromisoformat(end)
    except:
        await ctx.respond("Invalid timestamp format! Use YYYY-MM-DDTHH:MM")
        return
    filtered = [e for e in data["entries"] if start_dt <= datetime.fromisoformat(e["timestamp"]) <= end_dt]
    if name.lower() != "all":
        filtered = [e for e in filtered if e["name"].lower() == name.lower()]
    if not filtered:
        await ctx.respond("No entries found.")
        return
    table = "Name | Value | Timestamp\n--- | --- | ---\n"
    for e in filtered:
        table += f"{e['name']} | {e['value']} | {e['timestamp']}\n"
    await ctx.respond(f"```\n{table}\n```")

@bot.slash_command(name="graph", description="Show a graph for a name or all names")
@option("start", str, description="Start timestamp YYYY-MM-DDTHH:MM")
@option("end", str, description="End timestamp YYYY-MM-DDTHH:MM")
@option("name", str, description="Name to graph or 'all' for all names")
async def graph(ctx, start, end, name):
    try:
        start_dt = datetime.fromisoformat(start)
        end_dt = datetime.fromisoformat(end)
    except:
        await ctx.respond("Invalid timestamp format! Use YYYY-MM-DDTHH:MM")
        return
    filtered = [e for e in data["entries"] if start_dt <= datetime.fromisoformat(e["timestamp"]) <= end_dt]
    if name.lower() != "all":
        filtered = [e for e in filtered if e["name"].lower() == name.lower()]
    if not filtered:
        await ctx.respond("No entries found.")
        return
    plt.figure(figsize=(8,5))
    if name.lower() == "all":
        names = set(e["name"] for e in filtered)
        for n in names:
            vals = [e["value"] for e in filtered if e["name"]==n]
            times = [e["timestamp"][11:16] for e in filtered if e["name"]==n]
            plt.plot(times, vals, marker='o', label=n)
        plt.legend()
    else:
        vals = [e["value"] for e in filtered]
        times = [e["timestamp"][11:16] for e in filtered]
        plt.plot(times, vals, marker='o')
    plt.title("Stats Graph")
    plt.xlabel("Time")
    plt.ylabel("Value")
    buf = BytesIO()
    plt.savefig(buf, format='png')
    buf.seek(0)
    await ctx.send(file=discord.File(buf, "graph.png"))
    plt.close()

@bot.slash_command(name="delete", description="Delete all entries for a name")
@option("name", str, description="Name to delete or 'all' for everything")
async def delete(ctx, name):
    global data
    if name.lower() == "all":
        data["entries"] = []
        save_data()
        await ctx.respond("All entries deleted.")
        return
    before = len(data["entries"])
    data["entries"] = [e for e in data["entries"] if e["name"].lower() != name.lower()]
    save_data()
    deleted_count = before - len(data["entries"])
    if deleted_count == 0:
        await ctx.respond(f"No entries found for '{name}'.")
    else:
        await ctx.respond(f"Deleted {deleted_count} entries for '{name}'.")

# -------------------
# Event listener for translation
# -------------------
@bot.event
async def on_message(message):
    if message.author.bot:
        return
    channel_id = str(message.channel.id)
    if channel_id in data["translate_channels"]:
        pair = data["translate_channels"][channel_id]
        translated = translate_message(message.content, pair)
        await message.channel.send(translated)
    await bot.process_commands(message)

# -------------------
# Run bot
# -------------------
TOKEN = os.getenv("DISCORD_TOKEN")
bot.run(TOKEN)

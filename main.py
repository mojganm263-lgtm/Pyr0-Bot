import discord
from discord.ext import commands
import json
from datetime import datetime
import matplotlib.pyplot as plt
from io import BytesIO
from threading import Thread
from flask import Flask
import os
from transformers import pipeline

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
intents.reactions = True
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
    if pair == "en-uk":
        if any("\u0400" <= c <= "\u04FF" for c in text):
            model_name = "Helsinki-NLP/opus-mt-uk-en"
        else:
            model_name = "Helsinki-NLP/opus-mt-en-uk"
    elif pair == "en-ko":
        if any("\uAC00" <= c <= "\uD7AF" for c in text):
            model_name = "Helsinki-NLP/opus-mt-ko-en"
        else:
            model_name = "Helsinki-NLP/opus-mt-en-ko"
    translator = pipeline("translation", model=model_name, device=-1)
    return translator(text, max_length=512)[0]['translation_text']

# -------------------
# Commands
# -------------------
@bot.command(name="setchannel")
async def setchannel(ctx, channel: discord.TextChannel, language_pair: str):
    if language_pair not in ["en-uk", "en-ko"]:
        await ctx.send("Invalid language pair! Use 'en-uk' or 'en-ko'.")
        return
    data["translate_channels"][str(channel.id)] = language_pair
    save_data()
    await ctx.send(f"Channel {channel.mention} set to {language_pair} translation.")

@bot.command(name="resetchannel")
async def resetchannel(ctx, channel: discord.TextChannel):
    removed = data["translate_channels"].pop(str(channel.id), None)
    save_data()
    if removed:
        await ctx.send(f"Removed {channel.mention} from translation channels.")
    else:
        await ctx.send(f"{channel.mention} was not a translation channel.")

@bot.command(name="channels")
async def channels(ctx):
    if not data["translate_channels"]:
        await ctx.send("No channels are set for translation.")
        return
    msg = "Translation channels:\n"
    for cid, pair in data["translate_channels"].items():
        ch = ctx.guild.get_channel(int(cid))
        if ch:
            msg += f"{ch.mention}: {pair}\n"
    await ctx.send(msg)

@bot.command(name="log")
async def log(ctx, name: str, value: int):
    entry = {"name": name, "value": value, "timestamp": datetime.utcnow().isoformat()}
    data["entries"].append(entry)
    save_data()
    await ctx.send(f"Logged {value} for {name} at {entry['timestamp']}.")

@bot.command(name="delete")
async def delete(ctx, name: str):
    global data
    if name.lower() == "all":
        data["entries"] = []
        save_data()
        await ctx.send("All entries deleted.")
        return
    before = len(data["entries"])
    data["entries"] = [e for e in data["entries"] if e["name"].lower() != name.lower()]
    save_data()
    deleted_count = before - len(data["entries"])
    if deleted_count == 0:
        await ctx.send(f"No entries found for '{name}'.")
    else:
        await ctx.send(f"Deleted {deleted_count} entries for '{name}'.")

@bot.command(name="report")
async def report(ctx, start: str, end: str, name: str):
    try:
        start_dt = datetime.fromisoformat(start)
        end_dt = datetime.fromisoformat(end)
    except:
        await ctx.send("Invalid timestamp format! Use YYYY-MM-DDTHH:MM")
        return
    filtered = [e for e in data["entries"] if start_dt <= datetime.fromisoformat(e["timestamp"]) <= end_dt]
    if name.lower() != "all":
        filtered = [e for e in filtered if e["name"].lower() == name.lower()]
    if not filtered:
        await ctx.send("No entries found.")
        return
    table = "Name | Value | Timestamp\n--- | --- | ---\n"
    for e in filtered:
        table += f"{e['name']} | {e['value']} | {e['timestamp']}\n"
    await ctx.send(f"```\n{table}\n```")

@bot.command(name="graph")
async def graph(ctx, start: str, end: str, name: str):
    try:
        start_dt = datetime.fromisoformat(start)
        end_dt = datetime.fromisoformat(end)
    except:
        await ctx.send("Invalid timestamp format! Use YYYY-MM-DDTHH:MM")
        return
    filtered = [e for e in data["entries"] if start_dt <= datetime.fromisoformat(e["timestamp"]) <= end_dt]
    if name.lower() != "all":
        filtered = [e for e in filtered if e["name"].lower() == name.lower()]
    if not filtered:
        await ctx.send("No entries found.")
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

@bot.command(name="addname")
async def addname(ctx, name: str):
    exists = any(e["name"].lower() == name.lower() for e in data["entries"])
    if exists:
        await ctx.send(f"'{name}' already exists in the log.")
        return
    data["entries"].append({"name": name, "value": None, "timestamp": None})
    save_data()
    await ctx.send(f"Added name '{name}'.")

@bot.command(name="listnames")
async def listnames(ctx):
    names = set(e["name"] for e in data["entries"])
    if not names:
        await ctx.send("No names in the log.")
        return
    await ctx.send("Names:\n" + "\n".join(names))

@bot.command(name="translate")
async def translate(ctx, *, text: str, pair: str):
    if pair not in ["en-uk", "en-ko"]:
        await ctx.send("Invalid pair! Use 'en-uk' or 'en-ko'.")
        return
    translated = translate_message(text, pair)
    await ctx.send(translated)

@bot.command(name="settings")
async def settings(ctx):
    msg = "Bot Settings:\n"
    if data["translate_channels"]:
        for cid, pair in data["translate_channels"].items():
            ch = ctx.guild.get_channel(int(cid))
            if ch:
                msg += f"{ch.mention}: {pair}\n"
    else:
        msg += "No channels set.\n"
    await ctx.send(msg)

@bot.command(name="help")
async def help_command(ctx):
    commands_list = [
        "/setchannel #channel en-uk/en-ko",
        "/resetchannel #channel",
        "/channels",
        "/log name value",
        "/delete name/all",
        "/report start end name/all",
        "/graph start end name/all",
        "/addname name",
        "/listnames",
        "/translate text pair",
        "/settings",
        "/help"
    ]
    await ctx.send("Commands:\n" + "\n".join(commands_list) + "\n\nFor reaction translation: 🇺🇦 = Ukrainian, 🇬🇧 = English, 🇰🇷 = Korean")

# -------------------
# Event listeners
# -------------------
@bot.event
async def on_message(message):
    if message.author.bot:
        return
    # Automatic translation in set channels
    channel_id = str(message.channel.id)
    if channel_id in data["translate_channels"]:
        pair = data["translate_channels"][channel_id]
        translated = translate_message(message.content, pair)
        await message.channel.send(translated)
    await bot.process_commands(message)

@bot.event
async def on_reaction_add(reaction, user):
    if user.bot:
        return
    emoji_to_pair = {
        "🇺🇦": "en-uk",
        "🇬🇧": "en-uk" if any("\u0400" <= c <= "\u04FF" for c in reaction.message.content) else "en-ko",
        "🇰🇷": "en-ko"
    }
    pair = emoji_to_pair.get(str(reaction.emoji))
    if not pair:
        return

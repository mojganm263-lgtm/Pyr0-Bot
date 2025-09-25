import discord
from discord.ext import commands
from discord.utils import get
import json
import matplotlib.pyplot as plt
from datetime import datetime
import os
import io

# ---------------- Bot Setup ---------------- #
intents = discord.Intents.default()
intents.message_content = True
intents.reactions = True

bot = commands.Bot(command_prefix="/", intents=intents)

DATA_FILE = "data.json"

# Load or initialize data
if os.path.exists(DATA_FILE):
    with open(DATA_FILE, "r") as f:
        data = json.load(f)
else:
    data = {
        "channels": [],  # List of channel IDs
        "numbers": {}    # { "name": [{"value": number, "timestamp": timestamp}, ...] }
    }

# ---------------- Utility ---------------- #
def save_data():
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)

def ensure_channel(ctx):
    return ctx.channel.id in data["channels"]

# ---------------- Commands ---------------- #
@bot.command(name="commands")
async def show_commands(ctx):
    help_text = """
**Bot Commands**
`/add <name> <number>` → Save a number under a name.
`/view <name>` → Show all saved numbers for a name.
`/viewall` → Show numbers for all names.
`/delete <name>` → Delete all data for a name.
`/graph <name>` → Generate a graph for a name.
`/table <name>` → Generate a table for a name.
`/setchannel` → Set current channel for bot use.
`/listchannels` → Show all set channels.
`/translate <lang> <text>` → Translate text. Supported: **en, ko, uk**

**Examples**
`/translate en 안녕하세요`
`/translate ko Hello`
`/translate uk How are you?`
React with 🇺🇸 🇰🇷 🇺🇦 to translate a message into that language.
"""
    await ctx.send(help_text)

@bot.command()
async def setchannel(ctx):
    if ctx.channel.id not in data["channels"]:
        data["channels"].append(ctx.channel.id)
        save_data()
        await ctx.send(f"Channel {ctx.channel.name} is now set for translations.")
    else:
        await ctx.send("This channel is already set.")

@bot.command()
async def listchannels(ctx):
    if not data["channels"]:
        await ctx.send("No channels have been set yet.")
        return
    msg = "Set channels:\n"
    for ch_id in data["channels"]:
        ch = bot.get_channel(ch_id)
        msg += f"- {ch.name if ch else ch_id}\n"
    await ctx.send(msg)

@bot.command()
async def add(ctx, name: str, number: float):
    if not ensure_channel(ctx):
        return
    if name not in data["numbers"]:
        data["numbers"][name] = []
    data["numbers"][name].append({
        "value": number,
        "timestamp": datetime.now().isoformat()
    })
    save_data()
    await ctx.send(f"Added {number} for {name}.")

@bot.command()
async def view(ctx, name: str):
    if not ensure_channel(ctx):
        return
    if name not in data["numbers"]:
        await ctx.send(f"No data for {name}.")
        return
    msg = f"Data for {name}:\n"
    for entry in data["numbers"][name]:
        msg += f"{entry['timestamp']}: {entry['value']}\n"
    await ctx.send(msg)

@bot.command()
async def viewall(ctx):
    if not ensure_channel(ctx):
        return
    if not data["numbers"]:
        await ctx.send("No numbers stored.")
        return
    msg = ""
    for name, entries in data["numbers"].items():
        msg += f"**{name}**\n"
        for entry in entries:
            msg += f"{entry['timestamp']}: {entry['value']}\n"
    await ctx.send(msg)

@bot.command()
async def delete(ctx, name: str):
    if not ensure_channel(ctx):
        return
    if name in data["numbers"]:
        del data["numbers"][name]
        save_data()
        await ctx.send(f"Deleted all data for {name}.")
    else:
        await ctx.send(f"No data for {name}.")

@bot.command()
async def graph(ctx, name: str):
    if not ensure_channel(ctx):
        return
    if name not in data["numbers"]:
        await ctx.send(f"No data for {name}.")
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
    await ctx.send(file=discord.File(fp=buf, filename=f"{name}_graph.png"))

@bot.command()
async def table(ctx, name: str):
    if not ensure_channel(ctx):
        return
    if name not in data["numbers"]:
        await ctx.send(f"No data for {name}.")
        return
    msg = f"**Table for {name}**\n"
    msg += "Time | Value\n"
    msg += "--- | ---\n"
    for entry in data["numbers"][name]:
        msg += f"{entry['timestamp']} | {entry['value']}\n"
    await ctx.send(msg)

# ---------------- Reactions for translation ---------------- #
LANG_FLAGS = {
    "🇺🇸": "en",
    "🇰🇷": "ko",
    "🇺🇦": "uk"
}

@bot.event
async def on_reaction_add(reaction, user):
    if user.bot:
        return
    if reaction.message.channel.id not in data["channels"]:
        return
    lang = LANG_FLAGS.get(str(reaction.emoji))
    if not lang:
        return
    # Simple translator placeholder; replace with your Hugging Face API call
    translated = f"[{lang} translation of]: {reaction.message.content}"
    await reaction.message.reply(translated)

# ---------------- Start Bot ---------------- #
DISCORD_TOKEN = os.environ.get("DISCORD_TOKEN")  # Set this in Render env variables
bot.run(DISCORD_TOKEN)

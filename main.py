import discord
from discord.ext import commands
import json
import datetime
import matplotlib.pyplot as plt
from io import BytesIO

# ----- Config -----
TOKEN = "YOUR_DISCORD_BOT_TOKEN"  # set as environment variable for security
bot = commands.Bot(command_prefix="/", intents=discord.Intents.all())

# JSON storage
DATA_FILE = "data.json"

# Load or initialize data
try:
    with open(DATA_FILE, "r") as f:
        data = json.load(f)
except FileNotFoundError:
    data = {
        "translation_channels": {},  # channel_id: lang_pair
        "numeric_data": {}  # name: [{timestamp: value}, ...]
    }

# ----- Helper functions -----
def save_data():
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)

def translate(text, target_lang):
    # Replace with your actual translation model
    # Example placeholder
    return f"[{target_lang} translation of]: {text}"

# ----- Commands -----
@bot.command(name="help")
async def help_command(ctx):
    help_text = """
**Pyr0-Bot Commands**

/setchannel [channel] [lang_pair]
> Example: /setchannel #translations en-uk
Sets a channel for automatic translations between English and Ukrainian or Korean.

/adddata [name] [value]
> Example: /adddata Alice 42
Adds numeric data to a name (timestamped).

/deletedata [name]
> Example: /deletedata Bob
Deletes all data for the specified name.

/compile [start_date] [end_date] [name/all]
> Example: /compile 2025-09-01 2025-09-25 all
Compiles data for the given period, either for one name or for all names.

/graph [name/all]
> Example: /graph Alice
Generates a visual graph of numeric data for a name or all names.

/table [name/all]
> Example: /table all
Generates a table of numeric data for a name or all names.

**Translation Reaction Feature**
React to any message in a set channel with:
🇺🇦 → English ↔ Ukrainian translation
🇰🇷 → English ↔ Korean translation
The bot will post the translation immediately below the message.
"""
    await ctx.send(help_text)

@bot.command(name="setchannel")
async def set_channel(ctx, channel: discord.TextChannel, lang_pair: str):
    data["translation_channels"][str(channel.id)] = lang_pair.lower()
    save_data()
    await ctx.send(f"Set {channel.mention} to translate {lang_pair}")

@bot.command(name="adddata")
async def add_data(ctx, name: str, value: float):
    entry = {"timestamp": str(datetime.datetime.utcnow()), "value": value}
    if name not in data["numeric_data"]:
        data["numeric_data"][name] = []
    data["numeric_data"][name].append(entry)
    save_data()
    await ctx.send(f"Added {value} to {name}")

@bot.command(name="deletedata")
async def delete_data(ctx, name: str):
    if name in data["numeric_data"]:
        del data["numeric_data"][name]
        save_data()
        await ctx.send(f"Deleted all data for {name}")
    else:
        await ctx.send(f"No data found for {name}")

@bot.command(name="compile")
async def compile_data(ctx, start_date: str, end_date: str, target: str):
    try:
        start = datetime.datetime.fromisoformat(start_date)
        end = datetime.datetime.fromisoformat(end_date)
    except ValueError:
        await ctx.send("Date format must be YYYY-MM-DD")
        return

    results = {}
    names = data["numeric_data"].keys() if target.lower() == "all" else [target]
    for name in names:
        results[name] = [
            entry["value"] for entry in data["numeric_data"].get(name, [])
            if start <= datetime.datetime.fromisoformat(entry["timestamp"]) <= end
        ]
    await ctx.send(f"Compiled data: {results}")

@bot.command(name="table")
async def table_data(ctx, target: str):
    names = data["numeric_data"].keys() if target.lower() == "all" else [target]
    table_text = ""
    for name in names:
        entries = data["numeric_data"].get(name, [])
        table_text += f"**{name}:**\n"
        for e in entries:
            table_text += f"{e['timestamp']}: {e['value']}\n"
    await ctx.send(table_text or "No data available.")

@bot.command(name="graph")
async def graph_data(ctx, target: str):
    names = data["numeric_data"].keys() if target.lower() == "all" else [target]
    plt.figure(figsize=(6,4))
    for name in names:
        entries = data["numeric_data"].get(name, [])
        if entries:
            timestamps = [datetime.datetime.fromisoformat(e["timestamp"]) for e in entries]
            values = [e["value"] for e in entries]
            plt.plot(timestamps, values, label=name)
    plt.legend()
    plt.tight_layout()
    buf = BytesIO()
    plt.savefig(buf, format="png")
    buf.seek(0)
    await ctx.send(file=discord.File(fp=buf, filename="graph.png"))
    plt.close()

# ----- Event listeners -----
@bot.event
async def on_message(message):
    # Ignore bot messages
    if message.author.bot:
        return

    # Check translation channels
    lang_pair = data["translation_channels"].get(str(message.channel.id))
    if lang_pair:
        src, tgt = lang_pair.split("-")
        translated = translate(message.content, tgt)
        await message.channel.send(translated)

    await bot.process_commands(message)

@bot.event
async def on_reaction_add(reaction, user):
    if user.bot:
        return
    message = reaction.message
    lang_pair = data["translation_channels"].get(str(message.channel.id))
    if not lang_pair:
        return

    if str(reaction.emoji) == "🇺🇦":
        translated = translate(message.content, "uk")
        await message.channel.send(translated)
    elif str(reaction.emoji) == "🇰🇷":
        translated = translate(message.content, "ko")
        await message.channel.send(translated)

# ----- Run bot -----
bot.run(TOKEN)

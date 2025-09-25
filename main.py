import os
import discord
from discord.ext import commands
import json
import datetime
import io
import matplotlib.pyplot as plt
from huggingface_hub import InferenceClient  # Your original translator

# ---------------- Hugging Face Translator ---------------- #
HF_KEY = os.getenv("HF_KEY")
translator_client = InferenceClient(HF_KEY)

def translate(text, target_lang):
    """Translate using your Hugging Face model."""
    # Replace with the model you used before
    model_id = "Helsinki-NLP/opus-mt-en-uk"  # Example, adapt for en↔uk & en↔ko
    if target_lang == "ko":
        model_id = "Helsinki-NLP/opus-mt-en-ko"
    elif target_lang == "en":
        model_id = "Helsinki-NLP/opus-mt-ko-en"  # adjust based on your setup
    elif target_lang == "uk":
        model_id = "Helsinki-NLP/opus-mt-en-uk"
    
    result = translator_client.text(text, model=model_id)
    return result["translation_text"] if "translation_text" in result else str(result)

# ---------------- JSON Storage ---------------- #
DATA_FILE = "data.json"
if not os.path.exists(DATA_FILE):
    with open(DATA_FILE, "w") as f:
        json.dump({"channels": [], "numbers": {}}, f)

def load_data():
    with open(DATA_FILE, "r") as f:
        return json.load(f)

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)

data = load_data()

# ---------------- Bot Setup ---------------- #
intents = discord.Intents.default()
intents.messages = True
intents.message_content = True
intents.reactions = True
bot = commands.Bot(command_prefix="/", intents=intents)

# ---------------- Commands ---------------- #

@bot.command()
async def help(ctx):
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
        save_data(data)
        await ctx.send(f"✅ {ctx.channel.name} set as translation/data channel.")
    else:
        await ctx.send("⚠️ Channel already set.")

@bot.command()
async def listchannels(ctx):
    if not data["channels"]:
        await ctx.send("⚠️ No channels set yet.")
        return
    channels = [f"<#{cid}>" for cid in data["channels"]]
    await ctx.send("📌 Set channels: " + ", ".join(channels))

@bot.command()
async def add(ctx, name: str, number: float):
    if name not in data["numbers"]:
        data["numbers"][name] = []
    data["numbers"][name].append({"value": number, "time": str(datetime.datetime.now())})
    save_data(data)
    await ctx.send(f"✅ Added {number} under **{name}**")

@bot.command()
async def view(ctx, name: str):
    if name not in data["numbers"]:
        await ctx.send("⚠️ No data for that name.")
        return
    records = data["numbers"][name]
    msg = "\n".join([f"{r['time']}: {r['value']}" for r in records])
    await ctx.send(f"📊 Data for **{name}**:\n{msg}")

@bot.command()
async def viewall(ctx):
    if not data["numbers"]:
        await ctx.send("⚠️ No data stored.")
        return
    for name, records in data["numbers"].items():
        msg = "\n".join([f"{r['time']}: {r['value']}" for r in records])
        await ctx.send(f"📊 **{name}**:\n{msg}")

@bot.command()
async def delete(ctx, name: str):
    if name in data["numbers"]:
        del data["numbers"][name]
        save_data(data)
        await ctx.send(f"🗑️ Deleted all data for **{name}**")
    else:
        await ctx.send("⚠️ No data for that name.")

@bot.command()
async def graph(ctx, name: str):
    if name not in data["numbers"] or not data["numbers"][name]:
        await ctx.send("⚠️ No data for that name.")
        return
    records = data["numbers"][name]
    times = [r["time"] for r in records]
    values = [r["value"] for r in records]
    plt.figure()
    plt.plot(times, values, marker="o")
    plt.xticks(rotation=45, ha="right")
    plt.title(f"Graph for {name}")
    plt.tight_layout()
    buf = io.BytesIO()
    plt.savefig(buf, format="png")
    buf.seek(0)
    await ctx.send(file=discord.File(buf, "graph.png"))
    buf.close()

@bot.command()
async def table(ctx, name: str):
    if name not in data["numbers"] or not data["numbers"][name]:
        await ctx.send("⚠️ No data for that name.")
        return
    records = data["numbers"][name]
    msg = "```\nTime\t\t\tValue\n"
    for r in records:
        msg += f"{r['time']}\t{r['value']}\n"
    msg += "```"
    await ctx.send(msg)

@bot.command()
async def translate(ctx, lang: str, *, text: str):
    if lang.lower() not in ["en", "ko", "uk"]:
        await ctx.send("⚠️ Supported languages: en, ko, uk")
        return
    result = translate(text, lang.lower())
    await ctx.send(f"🌐 {lang.upper()} → {result}")

# ---------------- Reaction Translator ---------------- #

@bot.event
async def on_reaction_add(reaction, user):
    if user.bot:
        return
    if reaction.message.channel.id not in data["channels"]:
        return

    lang_map = {
        "🇺🇸": "en",
        "🇰🇷": "ko",
        "🇺🇦": "uk"
    }

    if reaction.emoji in lang_map:
        try:
            result = translate(reaction.message.content, lang_map[reaction.emoji])
            await reaction.message.channel.send(f"{reaction.emoji} → {result}")
        except Exception:
            await reaction.message.channel.send("⚠️ Translation error.")

# ---------------- Run Bot ---------------- #
bot.run(os.getenv("DISCORD_TOKEN"))

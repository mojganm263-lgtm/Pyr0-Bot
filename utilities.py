# ---------- FILE: cogs/utilities.py ----------
from discord.ext import commands

# ---------- Utility Functions ----------
def split_long_message(msg: str, limit: int = 1800):
    """
    Splits long messages into chunks for Discord.
    """
    lines = msg.split("\n")
    chunks = []
    current = ""
    for line in lines:
        if len(current) + len(line) + 1 > limit:
            chunks.append(current)
            current = line + "\n"
        else:
            current += line + "\n"
    if current:
        chunks.append(current)
    return chunks

class UtilitiesCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

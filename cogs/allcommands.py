# ---------- FILE: cogs/allcommands.py ----------
import discord
from discord.ext import commands
from discord import app_commands

class AllCommandsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="allcommands", description="Displays a list of all available commands")
    async def allcommands(self, interaction: discord.Interaction):
        cmds = self.bot.tree.walk_commands()  # get all registered slash commands
        lines = []
        for cmd in cmds:
            if isinstance(cmd, app_commands.Command):
                # name and description only
                lines.append(f"/{cmd.name} → {cmd.description}")

        description = "\n".join(lines) if lines else "No commands found."
        embed = discord.Embed(title="All Available Commands", description=description, color=0x8B0000)
        await interaction.response.send_message(embed=embed, ephemeral=True)

async def setup(bot):
    await bot.add_cog(AllCommandsCog(bot))

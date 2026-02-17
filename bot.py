import os
import asyncio
import discord
from discord.ext import commands
from dotenv import load_dotenv
import config

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.default()
intents.members = True
intents.message_content = True


bot = commands.Bot(command_prefix="!", intents=intents)

EXTENSIONS = [
    "feats.welcome",
    "feats.roles",
    "feats.promos",
    "feats.lounge",
    "feats.rules_gate",
    "feats.goodbot",
    "feats.daily_doodle",
]

_synced = False

@bot.event
async def on_ready():
    global _synced
    if not _synced:
        guild = discord.Object(id=config.GUILD_ID)
        bot.tree.copy_global_to(guild=guild)
        synced = await bot.tree.sync(guild=guild)
        print(f"Synced {len(synced)} commands to the server.")
        _synced = True

    print(f"Artie is online as {bot.user} (id={bot.user.id})")

async def main():
    for ext in EXTENSIONS:
        await bot.load_extension(ext)
    await bot.start(TOKEN)

if __name__ == "__main__":
    asyncio.run(main())

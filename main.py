import discord
import logging
from discord.ext import commands
from config import TOKEN, GUILD
from setup_logging import setup_logging
from database import init_db

setup_logging()

log = logging.getLogger(__name__)

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix="!", intents=intents)


@bot.event
async def on_ready():
    synced = await bot.tree.sync(guild=GUILD)
    log.info(f"Logged in as {bot.user}")
    log.info(f"Synced {len(synced)} command(s)")


async def main():
    await init_db()
    async with bot:
        await bot.load_extension("cogs.registration_cog")
        await bot.load_extension("cogs.permissions_cog")
        await bot.start(TOKEN)


import asyncio

asyncio.run(main())

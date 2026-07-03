import discord
from discord.ext import commands
from config import TOKEN, GUILD
from repositories.registrations import RegistrationRepository
from repositories.people import PeopleRepository
from repositories.key_values import KeyValueRepository

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    synced = await bot.tree.sync(guild=GUILD)
    print(f"Logged in as {bot.user}")
    print(f"Synced {len(synced)} command(s)")

async def main():
    await PeopleRepository().create_table()
    await KeyValueRepository().create_table()
    await RegistrationRepository().create_table()

    async with bot:
        await bot.load_extension("cogs.registration_cog")
        await bot.start(TOKEN)


import asyncio
asyncio.run(main())

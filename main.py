import asyncio
import logging

import discord
from discord.ext import commands

from config import DB_PATH, GUILD, TOKEN
from database import Database
from services.citizen_service import CitizenService
from services.permission_service import PermissionService
from services.registration_service import RegistrationService
from setup_logging import setup_logging

setup_logging()

log = logging.getLogger(__name__)

class RoyalSteward(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True

        self.db = Database(DB_PATH)
        self.citizen_service = CitizenService(self.db)
        self.registration_service = RegistrationService(self.db, self.citizen_service)
        self.permission_service = PermissionService(self.db)

        super().__init__(
            command_prefix="!",
            intents=intents,
        )

    async def setup_hook(self) -> None:
        await self.db.connect()
        await self.load_extension("cogs.citizens_cog")
        await self.load_extension("cogs.registration_cog")
        await self.load_extension("cogs.permissions_cog")

        synced = await self.tree.sync(guild=GUILD)
        log.info(f"Logged in as {self.user}")
        log.info(f"Synced {len(synced)} command(s)")

    async def close(self):
        await self.db.close()
        await super().close()


async def main():
    bot = RoyalSteward()

    async with bot:
        await bot.start(TOKEN)

if __name__ == "__main__":
    asyncio.run(main())

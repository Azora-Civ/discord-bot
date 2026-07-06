import discord
import config as cfg
import discord.ext.commands as commands
import re

from models.permission import Permission, PermissionLevel
from services.permission_service import PermissionService

REGEX = re.compile(
    rf"^Running command `?` .*"
)

class PermissionCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.service = PermissionService(bot)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if not message.author.bot: return
        if message.author.id != cfg.KIRA_USER_ID: return

        match = REGEX.search(message.content)
        if match:
            command = match.group(1)
            parts = command.split()
            if parts[0] not in ['nlpp', 'nlip', 'nlrm']: return

            level = parts[3] if len(parts) > 3 else "DEFAULT"
            try:
                level = PermissionLevel[level.upper()]
            except KeyError:
                return

            perm = Permission(
                namelayer=parts[1],
                ign=parts[2],
                level=level,
            )

            await self.service.update_user_permission(perm)


async def setup(bot: commands.Bot):
    await bot.add_cog(PermissionCog(bot), guild=cfg.GUILD)

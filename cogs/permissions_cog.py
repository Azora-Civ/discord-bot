import logging
import re

import discord
import discord.ext.commands as commands
from discord import Member, app_commands

import config as cfg
from helpers.citizens import ign_from_user
from helpers.general import respond
from helpers.permissions import (
    corrected_namelayer,
    namelayer_permission_panel,
    resolve_permission_target,
    user_permission_panel,
)
from models.permission import Permission, PermissionLevel
from models.permission_group import GroupPermission
from models.ShownException import BadStateException
from ui.modals.namelayer_import_modal import NameLayerImportModal
from ui.panels.permission_commands_panel import permission_command_embeds

REGEX = re.compile(r"^Running command `(.+?)` as .+$")
log = logging.getLogger(__name__)


class PermissionsCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.service = bot.permission_service

    root_group = app_commands.Group(
        name="perms",
        description="Commands for binding a civ namelayer to a discord role.",
    )

    @root_group.command(
        name="set",
        description="[ADMIN] Set a permission to a namelayer for a player or role. (DEFAULT to unset)",
    )
    @app_commands.default_permissions(administrator=True)
    @app_commands.checks.has_permissions(administrator=True)
    async def set(
        self,
        interaction: discord.Interaction,
        namelayer: str,
        level: PermissionLevel,
        role: discord.Role | None = None,
        user: Member | None = None,
        ign: str | None = None,
    ):
        async with respond(interaction) as should_process:
            if not should_process:
                return

            if role is not None:
                await self.service.update_group_permission(
                    GroupPermission(
                        namelayer=namelayer,
                        role_id=role.id,
                        level=level,
                    )
                )

                await interaction.edit_original_response(
                    content=f"Successfully updated permissions for users with {role.mention} to {namelayer} {level}."
                )
                return

            ign, name = await resolve_permission_target(self.bot, ign=ign, user=user)

            await self.service.update_user_permission(
                Permission(
                    namelayer=namelayer,
                    ign=ign,
                    level=level,
                )
            )

            await interaction.edit_original_response(
                content=f"Successfully updated permissions for user {name} to {namelayer} {level}."
            )

    @root_group.command(name="import", description="[ADMIN] use the jsmacros bot to fully sync the permissions.")
    @app_commands.default_permissions(administrator=True)
    @app_commands.checks.has_permissions(administrator=True)
    async def import_memberships(self, interaction: discord.Interaction) -> None:
        async with respond(interaction, defer=False) as should_process:
            if not should_process:
                return

            all_groups = await self.bot.db.group_permissions.fetch_all()

            namelayers = list(set(group.namelayer for group in all_groups))

            if not namelayers:
                raise BadStateException("No NameLayers were found.")

            await interaction.response.send_modal(NameLayerImportModal(namelayers))

    @root_group.command(
        name="fix", description="[ADMIN] List commands needed to align the permissions for a player or namelayer."
    )
    @app_commands.default_permissions(administrator=True)
    @app_commands.checks.has_permissions(administrator=True)
    async def check(
        self,
        interaction: discord.Interaction,
        namelayer: str | None = None,
        user: Member | None = None,
        ign: str | None = None,
    ):
        async with respond(interaction) as should_process:
            if not should_process:
                return

            if namelayer is not None:
                await corrected_namelayer(self.bot, namelayer)

            user = user or interaction.user

            msg = await permission_command_embeds(self.bot, namelayer=namelayer, user=user, ign=ign)
            await interaction.edit_original_response(**msg)

    @root_group.command(
        name="list",
        description="[ADMIN] List the perms for a namelayer or player. Shows both what they should/shouldn't have.",
    )
    @app_commands.default_permissions(administrator=True)
    @app_commands.checks.has_permissions(administrator=True)
    async def list(
        self,
        interaction: discord.Interaction,
        namelayer: str | None = None,
        user: Member | None = None,
        ign: str | None = None,
    ) -> None:
        async with respond(interaction) as should_process:
            if not should_process:
                return

            if namelayer is not None:
                namelayer = await corrected_namelayer(self.bot, namelayer)

                await interaction.edit_original_response(
                    content=None, **await namelayer_permission_panel(self.bot, namelayer)
                )
                return

            ign, name = await resolve_permission_target(
                self.bot,
                ign=ign,
                user=interaction.user if user is None else user,
            )

            await interaction.edit_original_response(content=None, **await user_permission_panel(self.bot, ign, name))

    @root_group.command(name="me", description="List the namelayers you have perms to or alternatively should have.")
    async def mine(self, interaction: discord.Interaction):
        async with respond(interaction) as should_process:
            if not should_process:
                return

            ign = await ign_from_user(self.bot, interaction.user)
            await interaction.edit_original_response(
                content=None,
                **await user_permission_panel(self.bot, ign, interaction.user.mention),
            )

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if not message.author.bot:
            return
        if message.author.id != cfg.KIRA_USER_ID:
            return

        match = REGEX.search(message.content)
        if match:
            command = match.group(1)
            parts = command.split()
            if parts[0] not in ["nlpp", "nlip", "nlrm"]:
                return

            level = parts[3] if len(parts) > 3 else "DEFAULT"
            try:
                level = PermissionLevel[level.upper()]
            except KeyError:
                return

            namelayer = await self.bot.db.group_permissions.correct_namelayer(parts[1])

            if not namelayer:
                return

            perm = Permission(
                namelayer=namelayer,
                ign=parts[2],
                level=level,
            )

            await self.service.update_actual_user_permission(perm)


async def setup(bot: commands.Bot):
    await bot.add_cog(PermissionsCog(bot), guild=cfg.GUILD)

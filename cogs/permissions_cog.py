import re

import discord
import discord.ext.commands as commands
from discord import app_commands

import config as cfg
from helpers.general import processing_response
from models.permission import Permission, PermissionLevel
from models.permission_group import GroupPermission
from repositories.group_permissions import GroupPermissionsRepository
from services.permission_service import PermissionService
from ui.modals.namelayer_export_modal import NameLayerExportModal
from ui.panels.permission_commands_panel import permission_command_embeds

REGEX = re.compile(r"^Running command `(.+?)` as .+$")


class PermissionsCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.service = PermissionService(bot)

    root_group = app_commands.Group(
        name="permissions",
        description="Commands for binding a civ namelayer to a discord role.",
    )
    list_commands_group = app_commands.Group(
        name="list_commands",
        description="List civ commands needed to align permissions.",
        parent=root_group
    )

    @root_group.command(
        name="add-binding",
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def add_binding(
        self,
        interaction: discord.Interaction,
        namelayer: str,
        role: discord.Role,
        level: PermissionLevel,
    ):
        async with processing_response(interaction):
            await self.service.update_group_permission(
                GroupPermission(
                    namelayer=namelayer,
                    role_id=role.id,
                    level=level,
                )
            )

    @root_group.command(
        name="import-memberships",
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def import_memberships(
        self,
        interaction: discord.Interaction
    ) -> None:
        all_groups = await GroupPermissionsRepository().fetch_all()

        namelayers = list(set(group.namelayer for group in all_groups))

        if not namelayers:
            raise "No NameLayers were provided or found."

        await interaction.response.send_modal(
            NameLayerExportModal(namelayers)
        )


    @list_commands_group.command(
        name="user",
        description="[ADMIN] List namelayer commands needed to align one user's permissions.",
    )
    async def user_commands(
        self,
        interaction: discord.Interaction,
        ign: str,
    ):
        async with processing_response(interaction):
            commands_to_run = await self.service.get_user_permission_commands(ign)
            await _send_command_list(
                interaction,
                title=f"Commands to align permissions for {ign}",
                commands_to_run=commands_to_run,
            )


    @list_commands_group.command(
        name="namelayer",
        description="[ADMIN] List commands needed to align all members of a namelayer.",
    )
    async def namelayer_commands(
        self,
        interaction: discord.Interaction,
        namelayer: str,
    ):
        async with processing_response(interaction):
            corrected_namelayer = await GroupPermissionsRepository().correct_namelayer(namelayer)
            if corrected_namelayer is None:
                raise "Couldn't find namelayer: {}!".format(namelayer)

            commands_to_run = await self.service.get_namelayer_member_commands(corrected_namelayer)
            await _send_command_list(
                interaction,
                title=f"Commands to align namelayer {corrected_namelayer}",
                commands_to_run=commands_to_run,
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

            namelayer = await GroupPermissionsRepository().correct_namelayer(parts[1])

            if not namelayer:
                return

            perm = Permission(
                namelayer=namelayer,
                ign=parts[2],
                level=level,
            )

            await self.service.update_user_permission(perm)


async def _send_command_list(
    interaction: discord.Interaction,
    title: str,
    commands_to_run: list[str],
) -> None:
    embeds = permission_command_embeds(title, commands_to_run)
    await interaction.edit_original_response(embed=embeds[0], content=None)

    for embed in embeds[1:]:
        await interaction.followup.send(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(PermissionsCog(bot), guild=cfg.GUILD)

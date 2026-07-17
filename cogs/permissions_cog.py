import re
from email.charset import add_alias

import discord
import discord.ext.commands as commands
from discord import app_commands, Member

import config as cfg
from helpers.general import processing_response
from models.ShownException import NotFoundException, BadRequestException
from models.permission import Permission, PermissionLevel
from models.permission_group import GroupPermission
from repositories.group_permissions import GroupPermissionsRepository
from repositories.people import PeopleRepository
from repositories.permissions import PermissionsRepository
from services.permission_service import PermissionService
from ui.modals.namelayer_import_modal import NameLayerImportModal
from ui.panels.permission_commands_panel import permission_command_embeds
from ui.panels.permission_list import permission_list_members, permission_list_namelayers

REGEX = re.compile(r"^Running command `(.+?)` as .+$")


class PermissionsCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.service = PermissionService(bot)

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
        async with processing_response(interaction):
            if role is not None:
                await self.service.update_group_permission(
                    GroupPermission(
                        namelayer=namelayer,
                        role_id=role.id,
                        level=level,
                    )
                )

                await interaction.edit_original_response(
                    content=f"Successfully updated permissions for users with {role.mention} to {namelayer} {level}.")
                return

            name = ign
            if ign is None and user is not None:
                ign = await _ign_from_user(user)
                name = user.mention

            if ign is None:
                raise BadRequestException("Must pass either a role, ign or citizen")

            await self.service.update_user_permission(
                Permission(
                    namelayer=namelayer,
                    ign=ign,
                    level=level,
                )
            )

            await interaction.edit_original_response(
                content=f"Successfully updated permissions for user {name} to {namelayer} {level}.")


    @root_group.command(
        name="import",
        description="[ADMIN] use the jsmacros bot to fully sync the permissions."
    )
    @app_commands.default_permissions(administrator=True)
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
            NameLayerImportModal(namelayers)
        )


    @root_group.command(
        name="fix",
        description="[ADMIN] List commands needed to align the permissions for a player or namelayer."
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
        async with processing_response(interaction):
            if namelayer is not None:
                corrected_namelayer = await GroupPermissionsRepository().correct_namelayer(namelayer)
                if corrected_namelayer is None:
                    raise NotFoundException("Couldn't find namelayer: {}!".format(namelayer))

                await _send_command_list(
                    interaction,
                    title=f"Commands to align '{corrected_namelayer}' namelayer",
                    commands_to_run=await self.service.get_namelayer_member_commands(corrected_namelayer),
                )
                return

            if ign is None:
                if user is None:
                    user = interaction.user
                if user is None:
                    raise BadRequestException("Must pass either a role, ign or citizen.")

                ign = await _ign_from_user(user)

            name = user.mention if user else ign
            await _send_command_list(
                interaction,
                title=f"Commands to align permissions for {name}",
                commands_to_run=await self.service.get_user_permission_commands(ign),
            )

    @root_group.command(
        name="list",
        description="[ADMIN] List the perms for a namelayer or player. Shows both what they should/shouldn't have."
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
        async with processing_response(interaction):
            if namelayer is not None:
                namelayer = await GroupPermissionsRepository().correct_namelayer(namelayer)
                if namelayer is None:
                    raise NotFoundException("Couldn't find namelayer: {}!".format(namelayer))
                actual = await PermissionsRepository().fetch_by_namelayer(namelayer)
                target = await self.service.get_namelayer_members(namelayer)

                await interaction.edit_original_response(
                    content=None,
                    **permission_list_members(actual, target, namelayer)
                )
                return


            name = ign
            if ign is None:
                user = interaction.user if user is None else user
                ign = await _ign_from_user(user)
                name = user.mention

            actual = await PermissionsRepository().fetch_by_ign(ign)
            target = await self.service.get_user_permissions(ign)

            await interaction.edit_original_response(
                content=None,
                **permission_list_namelayers(actual, target, name)
            )

    @root_group.command(
        name="me",
        description="List the namelayers you have perms to or alternatively should have."
    )
    async def mine(self, interaction: discord.Interaction):
        async with processing_response(interaction):
            ign = await _ign_from_user(interaction.user)
            actual = await PermissionsRepository().fetch_by_ign(ign)
            target = await self.service.get_user_permissions(ign)
            await interaction.edit_original_response(
                embeds=permission_list_namelayers(actual, target, interaction.user.mention),
                content=None,
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

            await self.service.update_actual_user_permission(perm)


async def _send_command_list(
    interaction: discord.Interaction,
    title: str,
    commands_to_run: list[str],
) -> None:
    await interaction.edit_original_response(content=None, **permission_command_embeds(title, commands_to_run))

async def _ign_from_user(user: Member) -> str:
    p_repo = PeopleRepository()
    person = await p_repo.get_by_user_id(user.id)
    if not person:
        raise NotFoundException("User is not registered as a citizen/resident.")

    return person.in_game_name


async def setup(bot: commands.Bot):
    await bot.add_cog(PermissionsCog(bot), guild=cfg.GUILD)

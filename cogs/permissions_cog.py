import re

import discord
import discord.ext.commands as commands
from discord import Member, app_commands

import config as cfg
from cogs.citizens_cog import ign_from_user
from helpers.discord import get_guild, get_member
from helpers.general import processing_response
from models.permission import Permission, PermissionLevel
from models.permission_group import GroupPermission
from models.ShownException import BadRequestException, BadStateException, NotFoundException
from ui.modals.namelayer_import_modal import NameLayerImportModal
from ui.panels.permission_commands_panel import permission_command_embeds
from ui.panels.permission_list import permission_list_members, permission_list_namelayers

REGEX = re.compile(r"^Running command `(.+?)` as .+$")


class PermissionsCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.service = bot.permission_service

    async def _role_context_for_user(self, ign: str) -> dict[int, str]:
        citizen = await self.bot.db.citizens.fetch_by_ign(ign)
        if citizen is None or citizen.user_id is None:
            return {}

        member = await get_member(self.bot, citizen.user_id)
        if member is None:
            return {}

        return {role.id: role.mention for role in member.roles}

    async def _role_context_for_namelayer(
        self,
        namelayer: str,
    ) -> tuple[dict[int, list[str]], dict[int, str]]:
        group_permissions = [
            gp
            for gp in await self.bot.db.group_permissions.fetch_all()
            if gp.namelayer == namelayer
        ]
        people = await self.bot.db.citizens.fetch_all()
        ign_by_user_id = {
            person.user_id: person.in_game_name
            for person in people
            if person.user_id is not None
        }
        if not ign_by_user_id:
            return {}, {}

        guild = await get_guild(self.bot)
        members = await guild.query_members(
            user_ids=list(ign_by_user_id.keys()),
        )
        role_member_igns_by_id: dict[int, list[str]] = {}
        role_sources_by_id: dict[int, str] = {}

        for gp in group_permissions:
            role = guild.get_role(gp.role_id)
            if role is None:
                continue

            role_sources_by_id[role.id] = role.mention
            role_member_igns_by_id[role.id] = [
                ign_by_user_id[member.id]
                for member in members
                if member.id in ign_by_user_id
                and any(member_role.id == role.id for member_role in member.roles)
            ]

        return role_member_igns_by_id, role_sources_by_id

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
                ign = await ign_from_user(self.bot, user)
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
        all_groups = await self.bot.db.group_permissions.fetch_all()

        namelayers = list(set(group.namelayer for group in all_groups))

        if not namelayers:
            raise BadStateException("No NameLayers were found.")

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
                corrected_namelayer = await self.bot.db.group_permissions.correct_namelayer(namelayer)
                if corrected_namelayer is None:
                    raise NotFoundException(f"Couldn't find namelayer: {namelayer}!")

            user = user or interaction.user

            msg = await permission_command_embeds(self.bot, namelayer=namelayer, user=user, ign=ign)
            await interaction.edit_original_response(**msg)

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
                namelayer = await self.bot.db.group_permissions.correct_namelayer(namelayer)
                if namelayer is None:
                    raise NotFoundException(f"Couldn't find namelayer: {namelayer}!")
                actual = await self.bot.db.permissions.fetch_by_namelayer(namelayer)
                role_member_igns_by_id, role_sources_by_id = await self._role_context_for_namelayer(namelayer)
                target = await self.service.get_namelayer_members(
                    namelayer,
                    role_member_igns_by_id,
                    role_sources_by_id,
                )

                await interaction.edit_original_response(
                    content=None,
                    **permission_list_members(actual, target, namelayer)
                )
                return


            name = ign
            if ign is None:
                user = interaction.user if user is None else user
                ign = await ign_from_user(self.bot, user)
                name = user.mention

            actual = await self.bot.db.permissions.fetch_by_ign(ign)
            target = await self.service.get_user_permissions(
                ign,
                await self._role_context_for_user(ign),
            )

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
            ign = await ign_from_user(self.bot, interaction.user)
            actual = await self.bot.db.permissions.fetch_by_ign(ign)
            target = await self.service.get_user_permissions(
                ign,
                await self._role_context_for_user(ign),
            )
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

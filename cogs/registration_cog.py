import re

import discord
from discord import app_commands
from discord.ext import commands

import config as cfg
from helpers.general import processing_response
from repositories.key_values import KeyValueRepository
from services.registration_service import RegistrationService
from ui.modals.registration_duchy_modal import registration_duchy_modal
from ui.modals.registration_embed_modal import RegistrationEmbedModal
from ui.panels.registration_panel import get_embed_config, registration_panel
from ui.views.registration_response_view import RegistrationResponseView
from ui.views.registration_view import RegistrationView


class RegistrationCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.service = RegistrationService(bot)
        self.snitch_cache = False

    async def _set_snitch_regex(self):
        self.snitch_cache = True

        self.snitch_channel = await KeyValueRepository().get_int(
            key=cfg.REGISTRATION_SNITCH_CHANNEL_ID_KEY
        )

        snitch = await KeyValueRepository().get(key=cfg.REGISTRATION_SNITCH_NAME_KEY)
        snitch_group = await KeyValueRepository().get(key=cfg.REGISTRATION_SNITCH_GROUP_KEY)
        self.snitch_regex = re.compile(
            rf"`\[{re.escape(snitch_group)}\]`\s+\*\*(.+?)\*\*\s+is at {re.escape(snitch)}"
        )

    root_group = app_commands.Group(
        name="registration",
        description="Collection of commands used to configure citizen registration."
    )

    @root_group.command(
        name="edit-panel",
        description="[ADMIN] Edit the registration panel.",
    )
    @app_commands.default_permissions(administrator=True)
    @app_commands.checks.has_permissions(administrator=True)
    async def edit_panel(self, interaction: discord.Interaction):
        embed_config = await get_embed_config()

        await interaction.response.send_modal(
            RegistrationEmbedModal(embed_config)
        )


    @root_group.command(
        name="panel", description="[ADMIN] Setup the registration panel here."
    )
    @app_commands.default_permissions(administrator=True)
    @app_commands.checks.has_permissions(administrator=True)
    async def panel(self, interaction: discord.Interaction):
        async with processing_response(interaction):
            panel = await registration_panel()
            await interaction.channel.send(**panel)
            await interaction.edit_original_response(content="Registration panel posted.")


    @root_group.command(
        name="set-channel",
        description="[ADMIN] Setup where registration creates new threads for new registrations.",
    )
    @app_commands.default_permissions(administrator=True)
    @app_commands.checks.has_permissions(administrator=True)
    async def set_registration_channel(
        self, interaction: discord.Interaction, channel: discord.ForumChannel
    ):
        async with processing_response(interaction, ephemeral=False):
            await KeyValueRepository().set_int(key=cfg.REGISTRATION_FORUM_ID_KEY, value=channel.id)
            await interaction.edit_original_response(
                content=(
                    "Successfully updated the registration channel. Future registrations will now "
                    f"be made under: {channel.mention}"
                )
            )


    @root_group.command(
        name="set-snitch",
        description="[ADMIN] Setup the snitch to listen for and where to listen.",
    )
    @app_commands.default_permissions(administrator=True)
    @app_commands.checks.has_permissions(administrator=True)
    async def set_registration_snitch(
        self,
        interaction: discord.Interaction,
        snitch: str,
        snitch_group: str,
        channel: discord.TextChannel,
    ):
        async with processing_response(interaction, ephemeral=False):
            await KeyValueRepository().set(key=cfg.REGISTRATION_SNITCH_NAME_KEY, value=snitch)
            await KeyValueRepository().set(
                key=cfg.REGISTRATION_SNITCH_GROUP_KEY, value=snitch_group
            )
            await KeyValueRepository().set_int(
                key=cfg.REGISTRATION_SNITCH_CHANNEL_ID_KEY, value=channel.id
            )
            await self._set_snitch_regex()
            await interaction.edit_original_response(
                content=(
                    "Successfully updated the registration snitch. Will now listen to snitch hits "
                    f"of '{snitch}' on '{snitch_group}' in {channel.mention}."
                )
            )


    @root_group.command(
        name="set-roles",
        description="[ADMIN] Setup roles given when registrations are accepted.",
    )
    @app_commands.describe(
        resident_role="Role given to residents. Leave empty to clear.",
        citizen_role="Role given to citizens. Leave empty to clear.",
        member_role="Role given to both residents and citizens. Leave empty to clear.",
    )
    @app_commands.default_permissions(administrator=True)
    @app_commands.checks.has_permissions(administrator=True)
    async def set_registration_roles(
        self,
        interaction: discord.Interaction,
        resident_role: discord.Role | None = None,
        citizen_role: discord.Role | None = None,
        member_role: discord.Role | None = None,
    ):
        async with processing_response(interaction, ephemeral=False):
            roles = {
                cfg.REGISTRATION_RESIDENT_ROLE_ID_KEY: resident_role,
                cfg.REGISTRATION_CITIZEN_ROLE_ID_KEY: citizen_role,
                cfg.REGISTRATION_MEMBER_ROLE_ID_KEY: member_role,
            }

            repo = KeyValueRepository()
            for key, role in roles.items():
                if role is None:
                    await repo.delete(key)
                    continue

                await repo.set_int(key=key, value=role.id)

            await interaction.edit_original_response(
                content=(
                    "Successfully updated registration roles.\n"
                    f"Resident: {resident_role.mention if resident_role else 'None'}\n"
                    f"Citizen: {citizen_role.mention if citizen_role else 'None'}\n"
                    f"Resident/Citizen: {member_role.mention if member_role else 'None'}"
                )
            )

    @root_group.command(
        name="set-duchies",
        description="[ADMIN] Setup the duchies to consider for registration.",
    )
    @app_commands.default_permissions(administrator=True)
    @app_commands.checks.has_permissions(administrator=True)
    async def set_duchies(self, interaction: discord.Interaction):
        await interaction.response.send_modal(
            await registration_duchy_modal()
        )


    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if not self.snitch_cache:
            await self._set_snitch_regex()

        if self.snitch_channel != message.channel.id:
            return

        match = self.snitch_regex.search(message.content)
        if match:
            ign = match.group(1)
            await self.service.hit_registration_snitch(ign)

async def setup(bot: commands.Bot):
    await bot.add_cog(RegistrationCog(bot), guild=cfg.GUILD)
    bot.add_view(RegistrationView())
    bot.add_view(RegistrationResponseView())

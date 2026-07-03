import re

import discord
from discord import app_commands
from discord.ext import commands

import config as cfg
from repositories.key_values import KeyValueRepository
from ui.views.registration_response_view import RegistrationResponseView
from ui.views.registration_view import RegistrationView
from helpers.general import processing_response
from services.registration_service import RegistrationService


class RegistrationCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.service = RegistrationService(bot)
        self.snitch_cache = False

    async def _set_snitch_regex(self):
        self.snitch_cache = True

        self.snitch_channel = await KeyValueRepository().get_int(key=cfg.REGISTRATION_SNITCH_CHANNEL_ID_KEY)

        snitch = await KeyValueRepository().get(key=cfg.REGISTRATION_SNITCH_NAME_KEY)
        snitch_group = await KeyValueRepository().get(key=cfg.REGISTRATION_SNITCH_GROUP_KEY)
        self.snitch_regex = re.compile(fr"`\[{re.escape(snitch_group)}\]`\s+\*\*(.+?)\*\*\s+is at {re.escape(snitch)}")


    @app_commands.command(name="registration-panel", description="Setup the registration panel here.")
    @app_commands.checks.has_permissions(administrator=True)
    async def registration_panel(
            self,
            interaction: discord.Interaction
    ):
        async with processing_response(interaction):
            embed = discord.Embed(
                title="Azora Registration",
                description="Register as a citizen or resident.",
                color=discord.Color.blue(),
            )

            await interaction.channel.send(
                embed=embed,
                view=RegistrationView(),
            )
            await interaction.edit_original_response(
                content="Registration panel posted."
            )

    @app_commands.command(name="registration-set-channel", description="Setup where registration creates new threads for new registrations.")
    @app_commands.checks.has_permissions(administrator=True)
    async def set_registration_channel(
            self,
            interaction: discord.Interaction,
            channel: discord.ForumChannel
    ):
        async with processing_response(interaction, ephemeral=False):
            await KeyValueRepository().set_int(key=cfg.REGISTRATION_FORUM_ID_KEY, value=channel.id)
            await interaction.edit_original_response(
                content=f"Successfully updated the registration channel. Future registrations will now be made under: {channel.mention}"
            )


    @app_commands.command(name="registration-set-snitch", description="Setup the snitch to listen for and where to listen.")
    @app_commands.checks.has_permissions(administrator=True)
    async def set_registration_snitch(
            self,
            interaction: discord.Interaction,
            snitch: str,
            snitch_group: str,
            channel: discord.TextChannel
    ):
        async with processing_response(interaction, ephemeral=False):
            await KeyValueRepository().set(key=cfg.REGISTRATION_SNITCH_NAME_KEY, value=snitch)
            await KeyValueRepository().set(key=cfg.REGISTRATION_SNITCH_GROUP_KEY, value=snitch_group)
            await KeyValueRepository().set_int(key=cfg.REGISTRATION_SNITCH_CHANNEL_ID_KEY, value=channel.id)\

            await self._set_snitch_regex()
            await interaction.edit_original_response(
                content=f"Successfully updated the registration snitch. Will now listen to snitch hits of '{snitch}' on '{snitch_group}' in {channel.mention}."
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
            await self.service.hit_registration_snitch(self.bot, ign)


async def setup(bot: commands.Bot):
    await bot.add_cog(RegistrationCog(bot), guild=cfg.GUILD)
    bot.add_view(RegistrationView())
    bot.add_view(RegistrationResponseView())
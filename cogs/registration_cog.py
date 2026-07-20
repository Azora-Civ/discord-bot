import logging
import re

import discord
from discord import app_commands
from discord.ext import commands

import config as cfg
from helpers.discord import get_message, is_mod
from helpers.general import respond
from models.citizen import Citizen, Citizenship
from models.registration import Registration, RegistrationStatus
from models.ShownException import BadRequestException, BadStateException
from services.events import RegistrationChangedEvent
from ui.modals.registration_duchy_modal import registration_duchy_modal
from ui.modals.registration_embed_modal import RegistrationEmbedModal
from ui.panels.application_panel import registration_panel as application_panel
from ui.panels.permission_commands_panel import permission_command_embeds
from ui.panels.registration_panel import get_embed_config, registration_panel
from ui.views.registration_response_view import RegistrationResponseView
from ui.views.registration_view import RegistrationView

log = logging.getLogger(__name__)

STATUS_TAG_KEYS = {
    RegistrationStatus.ACCEPTED: cfg.REGISTRATION_ACCEPTED_TAG_ID,
    RegistrationStatus.PENDING: cfg.REGISTRATION_PENDING_TAG_ID,
    RegistrationStatus.REJECTED: cfg.REGISTRATION_REJECTED_TAG_ID,
}
CITIZENSHIP_TAG_KEYS = {
    Citizenship.PRIMARY_CITIZEN: cfg.REGISTRATION_PRIMARY_TAG_ID,
    Citizenship.SECONDARY_CITIZEN: cfg.REGISTRATION_SECONDARY_TAG_ID,
    Citizenship.RESIDENT: cfg.REGISTRATION_RESIDENCY_TAG_ID,
}


class RegistrationCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.service = bot.registration_service
        self.service.on_registration_changed.subscribe(self.handle_registration_changed)
        self.snitch_cache = False
        self.snitch_channel: int | None = None
        self.snitch_regex: re.Pattern[str] | None = None

    @property
    def key_values(self):
        return self.bot.db.key_values

    async def cog_load(self) -> None:
        self.bot.create_task(
            self.refresh_active_registration_posts(),
            name="refresh_active_registration_posts",
        )

    async def handle_registration_changed(self, event: RegistrationChangedEvent) -> None:
        await self.update_registration_message(event.registration)

    async def refresh_active_registration_posts(self) -> None:
        registrations = await self.bot.db.registrations.fetch_all()
        if not registrations:
            return

        log.info("Refreshing %d active registration post(s)", len(registrations))
        for registration in registrations:
            try:
                await self.update_registration_message(registration)
            except Exception:
                log.exception("Failed to refresh registration post: %s", registration.id)

    async def _set_snitch_regex(self):
        self.snitch_cache = True

        self.snitch_channel = await self.key_values.get_int(key=cfg.REGISTRATION_SNITCH_CHANNEL_ID_KEY)

        snitch = await self.key_values.get(key=cfg.REGISTRATION_SNITCH_NAME_KEY)
        snitch_group = await self.key_values.get(key=cfg.REGISTRATION_SNITCH_GROUP_KEY)

        if not snitch or not snitch_group:
            self.snitch_regex = None
            return

        self.snitch_regex = re.compile(rf"`\[{re.escape(snitch_group)}\]`\s+\*\*(.+?)\*\*\s+is at {re.escape(snitch)}")

    async def submit_citizen_application(self, registration: Registration):
        await self.service.submit_citizen_application(registration)

    async def reject_registration(self, registration: Registration):
        await self.service.reject_registration(registration)

    async def accept_registration(
        self,
        registration: Registration,
        force: bool,
    ):
        if not registration.data.snitch_hit and not force:
            raise BadStateException(
                "Registration snitch has not yet been hit. "
                f"Run `/registration approve force:True` to approve `{registration.in_game_name}` anyway."
            )

        citizen = await self.service.accept_registration(registration, force)
        return citizen

    async def _registration_from_thread(self, interaction: discord.Interaction) -> Registration:
        registration = await self.bot.db.registrations.fetch_by_thread_id(interaction.channel_id)
        if registration is None:
            raise BadStateException("This command must be used in a pending registration thread.")
        return registration

    async def _require_mod(self, interaction: discord.Interaction, action: str) -> None:
        if not await is_mod(interaction):
            raise BadRequestException(f"You are not permitted to {action} the registration.")

    async def _send_permission_commands(self, interaction: discord.Interaction, citizen: Citizen | None) -> None:
        if citizen is None:
            await interaction.edit_original_response(content="Registration was already accepted.")
            return

        msg = await permission_command_embeds(self.bot, ign=citizen.in_game_name)
        msg["content"] = f"Accepted `{citizen.in_game_name}`. Permission commands:"

        response = await interaction.edit_original_response(**msg)
        if view := msg.get("view"):
            view.message = response

    async def update_registration_message(self, registration: Registration):
        if cfg.REGISTRATION_FORUM_ID is None:
            raise BadStateException("Registration forum is not configured.")

        channel = self.bot.get_channel(cfg.REGISTRATION_FORUM_ID) or await self.bot.fetch_channel(
            cfg.REGISTRATION_FORUM_ID
        )

        if not isinstance(channel, discord.ForumChannel):
            raise BadStateException("Configured registration channel is not a forum channel.")

        msg = await application_panel(self.bot, self.bot.db, registration)
        tags = await self._registration_tags(channel, registration)

        if not registration.data.thread_id or not registration.data.message_id:
            thread_msg = dict(msg)
            if tags:
                thread_msg["applied_tags"] = tags

            thread_with_message = await channel.create_thread(**thread_msg)
            registration.data.thread_id = thread_with_message.thread.id
            registration.data.message_id = thread_with_message.message.id

            if registration.status == RegistrationStatus.PENDING:
                await self.service.save_registration(registration, dispatch_events=False)
            return

        message = await get_message(
            self.bot,
            registration.data.thread_id,
            registration.data.message_id,
        )

        if message is None:
            return

        await message.edit(**msg)
        if tags and isinstance(message.channel, discord.Thread):
            await message.channel.edit(applied_tags=tags)

    async def _registration_tags(
        self,
        channel: discord.ForumChannel,
        registration: Registration,
    ) -> list[discord.ForumTag]:
        tag_ids = [
            STATUS_TAG_KEYS[registration.status],
            CITIZENSHIP_TAG_KEYS[registration.citizenship_type],
        ]
        tags = []
        for tag_id in tag_ids:
            if tag_id is None:
                continue

            tag = _forum_tag_by_id(channel, tag_id)
            if tag is not None:
                tags.append(tag)

        return tags

    root_group = app_commands.Group(
        name="registration",
        description="Collection of commands used to configure citizen registration.",
    )

    @root_group.command(
        name="edit-panel",
        description="[ADMIN] Edit the registration panel.",
    )
    @app_commands.default_permissions(administrator=True)
    @app_commands.checks.has_permissions(administrator=True)
    async def edit_panel(self, interaction: discord.Interaction):
        async with respond(interaction, defer=False) as should_process:
            if not should_process:
                return

            embed_config = await get_embed_config(self.bot.db)

            await interaction.response.send_modal(RegistrationEmbedModal(self.bot.db, embed_config))

    @root_group.command(
        name="approve",
        description="[MOD] Approve the registration in this thread.",
    )
    @app_commands.describe(force="Approve even if the registration snitch has not been hit.")
    async def approve(self, interaction: discord.Interaction, force: bool = False):
        async with respond(interaction) as should_process:
            if not should_process:
                return

            await self._require_mod(interaction, "approve")
            registration = await self._registration_from_thread(interaction)
            citizen = await self.accept_registration(registration, force)
            await self._send_permission_commands(interaction, citizen)

    @root_group.command(
        name="deny",
        description="[MOD] Deny the registration in this thread.",
    )
    async def deny(self, interaction: discord.Interaction):
        async with respond(interaction) as should_process:
            if not should_process:
                return

            await self._require_mod(interaction, "deny")
            registration = await self._registration_from_thread(interaction)
            await self.reject_registration(registration)
            await interaction.edit_original_response(content=f"Denied `{registration.in_game_name}`.")

    @root_group.command(name="panel", description="[ADMIN] Setup the registration panel here.")
    @app_commands.default_permissions(administrator=True)
    @app_commands.checks.has_permissions(administrator=True)
    async def panel(self, interaction: discord.Interaction):
        async with respond(interaction) as should_process:
            if not should_process:
                return

            panel = await registration_panel(self.bot.db)
            await interaction.channel.send(**panel)
            await interaction.edit_original_response(content="Registration panel posted.")

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
        async with respond(interaction, ephemeral=False) as should_process:
            if not should_process:
                return

            await self.key_values.set(key=cfg.REGISTRATION_SNITCH_NAME_KEY, value=snitch)
            await self.key_values.set(key=cfg.REGISTRATION_SNITCH_GROUP_KEY, value=snitch_group)
            await self.key_values.set_int(key=cfg.REGISTRATION_SNITCH_CHANNEL_ID_KEY, value=channel.id)
            await self._set_snitch_regex()
            await interaction.edit_original_response(
                content=(
                    "Successfully updated the registration snitch. Will now listen to snitch hits "
                    f"of '{snitch}' on '{snitch_group}' in {channel.mention}."
                )
            )

    @root_group.command(
        name="set-duchies",
        description="[ADMIN] Setup the duchies to consider for registration.",
    )
    @app_commands.default_permissions(administrator=True)
    @app_commands.checks.has_permissions(administrator=True)
    async def set_duchies(self, interaction: discord.Interaction):
        async with respond(interaction, defer=False) as should_process:
            if not should_process:
                return

            await interaction.response.send_modal(await registration_duchy_modal(self.bot.db))

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.id != cfg.KIRA_USER_ID:
            return

        if not self.snitch_cache:
            await self._set_snitch_regex()

        if self.snitch_channel != message.channel.id or self.snitch_regex is None:
            return

        match = self.snitch_regex.search(message.content)
        if match:
            ign = match.group(1)
            await self.service.hit_registration_snitch(ign)


async def setup(bot: commands.Bot):
    await bot.add_cog(RegistrationCog(bot), guild=cfg.GUILD)
    bot.add_view(RegistrationView())
    bot.add_view(RegistrationResponseView())


def _forum_tag_by_id(channel: discord.ForumChannel, tag_id: int) -> discord.ForumTag | None:
    return next((tag for tag in channel.available_tags if tag.id == tag_id), None)

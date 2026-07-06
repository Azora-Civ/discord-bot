import logging

import discord
from discord import Member
from discord.ext import commands

import config as cfg
from models.person import Person, Citizenship
from models.registration import Registration, RegistrationStatus
from repositories.key_values import KeyValueRepository
from repositories.people import PeopleRepository
from repositories.registrations import RegistrationRepository
from ui.panels.registration_panel import registration_panel
from ui.views.registration_force_accept import RegistrationForceAcceptView

log = logging.getLogger(__name__)


class RegistrationService:
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def request_registration(
        self, interaction: discord.Interaction, registration: Registration
    ):
        r_repo = RegistrationRepository()
        p_repo = PeopleRepository()
        user_id = registration.user_id

        # # Get person and create if they are new
        person = await p_repo.get_by_user_id(user_id)

        # If already citizen count snitch as hit
        registration.snitch_hit = person is not None and person.in_game_name == registration.in_game_name

        # Reject pending registration for this person
        previous_registrations = await r_repo.get_by_user_id(user_id)
        for reg in previous_registrations:
            if reg.status != RegistrationStatus.PENDING:
                continue
            await self.reject_registration(interaction.client, registration)

        # Confirm registration
        await self.update_registration_message(interaction.client, registration)
        await r_repo.create(registration)
        await interaction.edit_original_response(content="Registration request submitted!")

    async def update_registration_message(self, client: discord.Client, registration: Registration):
        forum_id = await KeyValueRepository().get_int(cfg.REGISTRATION_FORUM_ID_KEY)
        assert forum_id is not None, "Registration forum is not configured."

        channel = client.get_channel(forum_id) or await client.fetch_channel(forum_id)
        assert isinstance(channel, discord.ForumChannel), (
            "Configured registration channel is not a forum channel."
        )

        msg = registration_panel(registration)

        # Case 1: new registration create forum thread + starter message
        if (
            registration.id is None
            or registration.thread_id is None
            or registration.message_id is None
        ):
            thread_with_message = await channel.create_thread(
                name=f"Registration - {registration.in_game_name}", **msg
            )

            registration.thread_id = thread_with_message.thread.id
            registration.message_id = thread_with_message.message.id
            return

        # Check if thread exists
        try:
            thread = client.get_channel(registration.thread_id) or await client.fetch_channel(
                registration.thread_id
            )

        # Case 2: Thread no longer exists
        except discord.NotFound:
            # Thread was deleted
            await self.reject_registration(client, registration)
            return

        if not isinstance(thread, discord.Thread):
            await self.reject_registration(client, registration)
            return

        # Case 3: message exists, try to edit it
        try:
            message = await thread.fetch_message(registration.message_id)
            await message.edit(**msg)

        # Case 4: thread exists, but no message is known
        except discord.NotFound:
            # Message was deleted, but thread still exists
            message = await thread.send(**msg)
            registration.message_id = message.id

    async def accept_registration(
        self, interaction: discord.Interaction, registration: Registration, force: bool
    ):
        r_repo = RegistrationRepository()
        p_repo = PeopleRepository()

        if not registration.snitch_hit and not force:
            await interaction.edit_original_response(
                content=f"Snitch has not yet been hit for this person! Therefore, the in-game '{registration.in_game_name}' is unconfirmed.",
                view=RegistrationForceAcceptView(),
            )
            return

        # Update person
        person = await p_repo.get_by_user_id(registration.user_id) or Person(
            user_id=registration.user_id,
            in_game_name=registration.in_game_name,
            citizenship=registration.citizenship_type
        )
        person.citizenship = registration.citizenship_type
        await p_repo.upsert(person)

        try:
            guild = interaction.guild
            member: Member = guild.get_member(person.user_id) or await guild.fetch_member(
                person.user_id
            )
            await member.edit(nick=registration.in_game_name)
        except:
            log.exception("Failed to edit nickname")

        # Update registration
        registration.status = RegistrationStatus.ACCEPTED
        await r_repo.delete(registration.id)
        await self.update_registration_message(interaction.client, registration)

    async def reject_registration(self, client: discord.Client, registration: Registration):
        if registration is None:
            return

        if registration.status == RegistrationStatus.REJECTED:
            return

        r_repo = RegistrationRepository()

        # Update registration
        registration.status = RegistrationStatus.REJECTED
        await self.update_registration_message(client, registration)
        await r_repo.delete(registration.id)

    async def hit_registration_snitch(self, bot: discord.Client, ign: str):
        r_repo = RegistrationRepository()
        registration = await r_repo.get_by_ign(ign)
        if registration is None:
            return

        registration.snitch_hit = True
        await self.update_registration_message(bot, registration)
        await r_repo.update(registration)

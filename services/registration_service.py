import discord
from discord.ext import commands

import config as cfg
from models.person import Person, Citizenship
from models.registration import Registration, RegistrationStatus
from repositories.key_values import KeyValueRepository
from repositories.people import PeopleRepository
from repositories.registrations import RegistrationRepository
from ui.views.registration_force_accept import RegistrationForceAcceptView
from ui.views.registration_response_view import RegistrationResponseView

class RegistrationService:
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def request_registration(self, interaction: discord.Interaction, registration: Registration):
        r_repo = RegistrationRepository()
        p_repo = PeopleRepository()
        user_id = registration.user_id

        # Get person and create if they are new
        person = await p_repo.get_by_user_id(user_id)
        if person is None:
            person = Person(
                user_id=user_id,
                citizenship=Citizenship.PENDING,
                in_game_name=registration.in_game_name,
            )
            await p_repo.upsert(person)

        # If already citizen count snitch as hit
        registration.snitch_hit = person.citizenship != Citizenship.PENDING

        # Reject pending registration for this person
        previous_registrations = await r_repo.get_by_user_id(user_id)
        for reg in previous_registrations:
            if reg.status != RegistrationStatus.PENDING: continue
            await self.reject_registration(interaction.client, registration)


        # Confirm registration
        await self.update_registration_message(interaction.client, registration)
        await r_repo.create(registration)
        await interaction.edit_original_response(content="Registration request submitted!")


    async def update_registration_message(self, client: discord.Client, registration: Registration):
        forum_id = await KeyValueRepository().get_int(cfg.REGISTRATION_FORUM_ID_KEY)
        assert forum_id is not None, "Registration forum is not configured."

        channel = client.get_channel(forum_id) or await client.fetch_channel(forum_id)
        assert isinstance(channel, discord.ForumChannel), "Configured registration channel is not a forum channel."

        msg = self._get_msg(registration)

        # Case 1: new registration create forum thread + starter message
        if registration.id is None or registration.thread_id is None or registration.message_id is None:
            thread_with_message = await channel.create_thread(
                name=f"Registration - {registration.in_game_name}",
                **msg
            )

            registration.thread_id = thread_with_message.thread.id
            registration.message_id = thread_with_message.message.id
            return

        # Check if thread exists
        try:
            thread = client.get_channel(registration.thread_id) or await client.fetch_channel(registration.thread_id)

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


    async def accept_registration(self, interaction: discord.Interaction, registration: Registration, force: bool):
        r_repo = RegistrationRepository()
        p_repo = PeopleRepository()

        if not registration.snitch_hit and not force:
            await interaction.edit_original_response(
                content=f"Snitch has not yet been hit for this person! Therefore, the in-game '{registration.in_game_name}' is unconfirmed.",
                view=RegistrationForceAcceptView()
            )
            return

        # Update person
        person = await p_repo.get_by_user_id(registration.user_id)
        person.citizenship = registration.citizenship_type
        await p_repo.update(person)

        # Update registration
        registration.status = RegistrationStatus.ACCEPTED
        await r_repo.delete(registration.id)
        await self.update_registration_message(interaction.client, registration)


    async def reject_registration(self, client: discord.Client, registration: Registration):
        if registration.status == RegistrationStatus.REJECTED:
            return

        r_repo = RegistrationRepository()
        p_repo = PeopleRepository()

        # Update person (delete if not already citizen)
        person = await p_repo.get_by_user_id(registration.user_id)
        if person.citizenship is Citizenship.PENDING:
            await p_repo.delete(person)

        # Update registration
        registration.status = RegistrationStatus.REJECTED
        await r_repo.delete(registration.id)
        await self.update_registration_message(client, registration)


    async def hit_registration_snitch(self, bot: discord.Client, ign: str):
        r_repo = RegistrationRepository()
        registration = await r_repo.get_by_ign(ign)
        if registration is None:
            return

        registration.snitch_hit = True
        await self.update_registration_message(bot, registration)
        await r_repo.update(registration)


    def _get_msg(self, registration: Registration):
        embed = discord.Embed(
            title="New Registration Request",
            description=f"<@{registration.user_id}> submitted a registration request.",
            color=discord.Color.gold(),
        )

        embed.add_field(name="In-game name", value=registration.in_game_name, inline=False)
        embed.add_field(name="Requested status", value=registration.citizenship_type, inline=False)
        embed.add_field(name="What goals/skills do you bring to Azora?", value=registration.about, inline=False)
        embed.add_field(
            name="Do you promise to follow the rules?",
            value=registration.follow_rules,
            inline=False,
        )
        embed.add_field(
            name="Citizens/Residents start at Level 1. Understand?",
            value=registration.citizenry,
            inline=False,
        )

        embed.add_field(
            name="Status:",
            value=str(registration.status),
            inline=False
        )

        embed.add_field(
            name="Hit a snitch:",
            value=str(registration.snitch_hit),
            inline=False
        )

        return {
            "embed": embed,
            "view": RegistrationResponseView()
        }
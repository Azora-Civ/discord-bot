import logging

import discord
from discord import Member
from discord.ext import commands

import config as cfg
from models.person import Citizenship, Person
from models.registration import Registration, RegistrationStatus
from repositories.key_values import KeyValueRepository
from repositories.people import PeopleRepository
from repositories.registrations import RegistrationRepository
from services.permission_service import PermissionService
from ui.panels.permission_commands_panel import permission_command_embeds
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
        registration.snitch_hit = (
            person is not None and person.in_game_name == registration.in_game_name
        )

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
                content=(
                    "Snitch has not yet been hit for this person! Therefore, the in-game "
                    f"'{registration.in_game_name}' is unconfirmed."
                ),
                view=RegistrationForceAcceptView(),
            )
            return

        # Update person
        person = await p_repo.get_by_user_id(registration.user_id) or Person(
            user_id=registration.user_id,
            in_game_name=registration.in_game_name,
            citizenship=registration.citizenship_type,
        )
        person.citizenship = registration.citizenship_type
        await p_repo.upsert(person)

        member = await self._fetch_member(interaction.guild, person.user_id)
        if member is not None:
            try:
                await member.edit(nick=registration.in_game_name)
            except discord.DiscordException:
                log.exception("Failed to edit nickname after registration acceptance")

            try:
                await self._sync_registration_roles(member, person.citizenship)
            except discord.DiscordException:
                log.exception("Failed to update roles after registration acceptance")

            await self._send_permission_command_followup(interaction, person.in_game_name)

        # Update registration
        registration.status = RegistrationStatus.ACCEPTED
        await r_repo.delete(registration.id)
        await self.update_registration_message(interaction.client, registration)


    async def _fetch_member(self, guild: discord.Guild | None, user_id: int) -> Member | None:
        if guild is None:
            return None

        try:
            return guild.get_member(user_id) or await guild.fetch_member(user_id)
        except discord.DiscordException:
            log.exception("Failed to fetch member after registration acceptance")
            return None


    async def _sync_registration_roles(self, member: Member, citizenship: Citizenship):
        repo = KeyValueRepository()
        role_ids = {
            Citizenship.RESIDENT: await repo.get_int(cfg.REGISTRATION_RESIDENT_ROLE_ID_KEY),
            Citizenship.CITIZEN: await repo.get_int(cfg.REGISTRATION_CITIZEN_ROLE_ID_KEY),
            "member": await repo.get_int(cfg.REGISTRATION_MEMBER_ROLE_ID_KEY),
        }

        managed_role_ids = {role_id for role_id in role_ids.values() if role_id is not None}
        desired_role_ids = {
            role_ids["member"],
            role_ids.get(citizenship),
        } - {None}

        roles_to_add = [
            role
            for role_id in desired_role_ids
            if (role := member.guild.get_role(role_id)) is not None and role not in member.roles
        ]
        roles_to_remove = [
            role
            for role in member.roles
            if role.id in managed_role_ids and role.id not in desired_role_ids
        ]

        if roles_to_remove:
            await member.remove_roles(
                *roles_to_remove,
                reason="Registration citizenship role changed",
            )
        if roles_to_add:
            await member.add_roles(
                *roles_to_add,
                reason="Registration accepted",
            )

    async def _send_permission_command_followup(
        self,
        interaction: discord.Interaction,
        in_game_name: str,
    ) -> None:
        commands = await PermissionService(self.bot).get_user_permission_commands(in_game_name)
        embeds = permission_command_embeds(
            f"Commands to align permissions for {in_game_name}",
            commands,
        )

        for embed in embeds:
            await interaction.followup.send(embed=embed, ephemeral=True)


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

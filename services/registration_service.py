import logging

import discord
from discord import Member
from discord.ext import commands

import config as cfg
from helpers.discord import get_member, get_message
from models.citizen import Citizen, Citizenship
from models.registration import Registration, RegistrationStatus
from models.ShownException import BadRequestException, BadStateException
from repositories.citizens import CitizenRepository
from repositories.key_values import KeyValueRepository
from repositories.registrations import RegistrationRepository
from ui.panels.application_panel import registration_panel
from ui.views.registration_force_accept import RegistrationForceAcceptView

log = logging.getLogger(__name__)


class RegistrationService:
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def submit_citizen_application(self, registration: Registration):
        r_repo = RegistrationRepository()
        c_repo = CitizenRepository()

        # Fetch the stored version so we can detect changes.
        existing = (
            await r_repo.fetch_by_id(registration.id)
            if registration.id is not None
            else None
        )

        # The Discord user must not already be a citizen.
        if registration.is_for_self:
            citizen = await c_repo.fetch_by_user_id(registration.poster_id)
            if citizen is not None:
                raise BadRequestException("You are already a citizen!")

        # The requested IGN must not belong to any citizen.
        citizen = await c_repo.fetch_by_ign(registration.in_game_name)
        if citizen is not None:
            raise BadRequestException(
                "That in-game name already belongs to a citizen!"
            )

        # The Discord user must not have another registration.
        if registration.is_for_self:
            conflict = await r_repo.fetch_by_user_id(registration.poster_id)

            if conflict is not None and conflict.id != registration.id:
                raise BadRequestException(
                    "You already have a citizen application!"
                )

        # The requested IGN must not be used by another registration.
        conflict = await r_repo.fetch_by_ign(registration.in_game_name)

        if conflict is not None and conflict.id != registration.id:
            raise BadRequestException(
                "That in-game name is already used in another application!"
            )

        # A snitch hit for the old IGN says nothing about the new IGN.
        if (
                existing is not None
                and existing.in_game_name
                != registration.in_game_name
        ):
            registration.data.snitch_hit = False

        await self._update_registration(registration)


    async def _update_registration(self, registration: Registration):
        await self._update_registration_message(registration)

        is_new = registration.id is None
        keep = registration.status == RegistrationStatus.PENDING

        r_repo = RegistrationRepository()
        if is_new and keep:
            registration.id = await r_repo.create(registration)
        elif not is_new and keep:
            await r_repo.update(registration)
        elif not is_new and not keep:
            await r_repo.delete(registration.id)


    async def _update_registration_message(self, registration: Registration):
        bot = self.bot

        forum_id = await KeyValueRepository().get_int(cfg.REGISTRATION_FORUM_ID_KEY)
        if forum_id is None:
            raise BadStateException("Registration forum is not configured.")

        channel = bot.get_channel(forum_id) or await bot.fetch_channel(forum_id)

        if not isinstance(channel, discord.ForumChannel):
            raise BadStateException("Configured registration channel is not a forum channel.")

        msg = await registration_panel(bot, registration)

        # Create thread
        if registration.id is None:
            thread_with_message = await channel.create_thread(**msg)
            registration.data.thread_id = thread_with_message.thread.id
            registration.data.message_id = thread_with_message.message.id
            return

        # Fetch old message and edit
        message = None
        if registration.data.thread_id and registration.data.message_id:
            message = await get_message(
                bot,
                registration.data.thread_id,
                registration.data.message_id,
            )

        if message is None:
            await self.reject_registration(registration)
            return

        await message.edit(**msg)


    async def reject_registration(self, registration: Registration):
        if registration.status == RegistrationStatus.REJECTED:
            return

        # Update registration
        registration.status = RegistrationStatus.REJECTED
        await self._update_registration(registration)


    async def accept_registration(
        self, registration: Registration, force: bool
    ):
        if registration.status == RegistrationStatus.ACCEPTED:
            return

        c_repo = CitizenRepository()

        if not registration.data.snitch_hit and not force:
            raise BadStateException(
                content="Snitch has not yet been hit for this person! Therefore, the in-game "
                f"'{registration.in_game_name}' is unconfirmed.",
                view=RegistrationForceAcceptView(),
            )

        # Add citizen
        citizen = Citizen(
            user_id=registration.poster_id if registration.is_for_self else None,
            in_game_name=registration.in_game_name,
            citizenship=registration.citizenship_type
        )

        await c_repo.create(citizen)

        registration.status = RegistrationStatus.ACCEPTED
        await self._update_registration(registration)

        if citizen.user_id is None:
            return

        member = await get_member(self.bot, citizen.user_id)
        if member is not None:
            try:
                await member.edit(nick=registration.in_game_name)
            except discord.DiscordException:
                log.exception("Failed to edit nickname after registration acceptance")

            try:
                await self._sync_registration_roles(member, citizen.citizenship)
            except discord.DiscordException:
                log.exception("Failed to update roles after registration acceptance")


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
                reason="Citizenship changed",
            )
        if roles_to_add:
            await member.add_roles(
                *roles_to_add,
                reason="Citizenship changed",
            )


    async def hit_registration_snitch(self, ign: str):
        r_repo = RegistrationRepository()
        registration = await r_repo.fetch_by_ign(ign)
        if registration is None:
            return

        registration.data.snitch_hit = True
        await self._update_registration(registration)

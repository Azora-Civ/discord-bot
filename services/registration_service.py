from typing import TYPE_CHECKING

from models.citizen import Citizen
from models.registration import Registration, RegistrationStatus
from models.ShownException import BadRequestException, BadStateException

if TYPE_CHECKING:
    from database import Database


class RegistrationService:
    def __init__(self, db: "Database"):
        self.db = db

    async def submit_citizen_application(self, registration: Registration) -> Registration:
        # Fetch the stored version so we can detect changes.
        existing = (
            await self.db.registrations.fetch_by_id(registration.id)
            if registration.id is not None
            else None
        )

        # The Discord user must not already be a citizen.
        if registration.is_for_self:
            citizen = await self.db.citizens.fetch_by_user_id(registration.poster_id)
            if citizen is not None:
                raise BadRequestException("You are already a citizen!")

        # The requested IGN must not belong to any citizen.
        citizen = await self.db.citizens.fetch_by_ign(registration.in_game_name)
        if citizen is not None:
            raise BadRequestException(
                "That in-game name already belongs to a citizen!"
            )

        # The Discord user must not have another registration.
        if registration.is_for_self:
            conflict = await self.db.registrations.fetch_by_user_id(registration.poster_id)

            if conflict is not None and conflict.id != registration.id:
                raise BadRequestException(
                    "You already have a citizen application!"
                )

        # The requested IGN must not be used by another registration.
        conflict = await self.db.registrations.fetch_by_ign(registration.in_game_name)

        if conflict is not None and conflict.id != registration.id:
            raise BadRequestException(
                "That in-game name is already used in another application!"
            )

        # A snitch hit for the old IGN says nothing about the new IGN.
        if (
            existing is not None
            and existing.in_game_name != registration.in_game_name
        ):
            registration.data.snitch_hit = False

        await self.save_registration(registration)
        return registration

    async def save_registration(self, registration: Registration) -> Registration:
        is_new = registration.id is None
        keep = registration.status == RegistrationStatus.PENDING

        if is_new and keep:
            registration.id = await self.db.registrations.create(registration)
        elif not is_new and keep:
            await self.db.registrations.update(registration)
        elif not is_new and not keep:
            await self.db.registrations.delete(registration.id)

        return registration

    async def reject_registration(self, registration: Registration) -> Registration:
        if registration.status == RegistrationStatus.REJECTED:
            return registration

        registration.status = RegistrationStatus.REJECTED
        await self.save_registration(registration)
        return registration

    async def accept_registration(
        self, registration: Registration, force: bool
    ) -> Citizen | None:
        if registration.status == RegistrationStatus.ACCEPTED:
            return None

        if not registration.data.snitch_hit and not force:
            raise BadStateException(
                "Snitch has not yet been hit for this person! Therefore, the in-game "
                f"'{registration.in_game_name}' is unconfirmed."
            )

        citizen = Citizen(
            user_id=registration.poster_id if registration.is_for_self else None,
            in_game_name=registration.in_game_name,
            citizenship=registration.citizenship_type,
        )

        await self.db.citizens.create(citizen)

        registration.status = RegistrationStatus.ACCEPTED
        await self.save_registration(registration)

        return citizen

    async def hit_registration_snitch(self, ign: str) -> Registration | None:
        registration = await self.db.registrations.fetch_by_ign(ign)
        if registration is None:
            return None

        registration.data.snitch_hit = True
        await self.save_registration(registration)
        return registration

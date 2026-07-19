from datetime import UTC, datetime, timedelta

import discord
from discord.ext import commands

from models.citizen import Citizen, Citizenship
from models.ShownException import BadRequestException, NotFoundException
from repositories.citizens import CitizenRepository


class CitizenService:
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.repo = CitizenRepository()

    async def list_citizens(self, ign: str | None = None) -> list[Citizen]:
        citizens = await self.repo.fetch_all()
        if ign is None or not ign.strip():
            return citizens

        needle = ign.strip().casefold()
        return [
            citizen
            for citizen in citizens
            if needle in citizen.in_game_name.casefold()
        ]

    async def get_citizen(
        self,
        *,
        citizen_id: int | None = None,
        ign: str | None = None,
        user: discord.User | discord.Member | None = None,
    ) -> Citizen:
        citizen = None

        if citizen_id is not None:
            citizen = await self.repo.fetch_by_id(citizen_id)
        elif ign is not None:
            citizen = await self.repo.fetch_by_ign(ign)
        elif user is not None:
            citizen = await self.repo.fetch_by_user_id(user.id)

        if citizen is None:
            raise NotFoundException("Citizen not found.")

        return citizen

    async def update_citizen(
        self,
        citizen: Citizen,
        *,
        in_game_name: str,
        user_id: int | None,
        citizenship: Citizenship,
    ) -> Citizen:
        if citizen.id is None:
            raise BadRequestException("Cannot update a citizen without an id.")

        in_game_name = in_game_name.strip()
        if not in_game_name:
            raise BadRequestException("In-game name cannot be empty.")

        ign_conflict = await self.repo.fetch_by_ign(in_game_name)
        if ign_conflict is not None and ign_conflict.id != citizen.id:
            raise BadRequestException("That in-game name already belongs to another citizen.")

        if user_id is not None:
            user_conflict = await self.repo.fetch_by_user_id(user_id)
            if user_conflict is not None and user_conflict.id != citizen.id:
                raise BadRequestException("That Discord user already belongs to another citizen.")

        citizen.in_game_name = in_game_name
        citizen.user_id = user_id
        citizen.citizenship = citizenship
        await self.repo.update(citizen)
        return citizen

    async def remove_citizen(self, citizen_id: int) -> Citizen:
        citizen = await self.get_citizen(citizen_id=citizen_id)
        await self.repo.delete(citizen_id)
        return citizen

    async def hit_snitch(self, ign: str) -> Citizen | None:
        citizen = await self.repo.fetch_by_ign(ign)
        if citizen is None:
            return None

        citizen.last_online = datetime.now(UTC)
        await self.repo.update(citizen)
        return citizen

    async def stats(self, active_days: int = 14) -> tuple[int, int]:
        if active_days < 1:
            raise BadRequestException("Active days must be at least 1.")

        citizens = await self.repo.fetch_all()
        cutoff = datetime.now(UTC) - timedelta(days=active_days)
        active = [
            citizen
            for citizen in citizens
            if _aware(citizen.last_online) >= cutoff
        ]
        return len(citizens), len(active)


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value

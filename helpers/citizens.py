import logging

from discord import Member
from discord.ext import commands

import config as cfg
from helpers.discord import get_member
from models.citizen import Citizen, Citizenship
from models.ShownException import NotFoundException


async def ign_from_user(bot: commands.Bot, user: Member) -> str:
    person = await bot.db.citizens.fetch_by_user_id(user.id)
    if not person:
        raise NotFoundException("User is not registered as a citizen/resident.")

    return person.in_game_name


async def citizenship_role_ids(db) -> dict[Citizenship | str, int | None]:
    return {
        Citizenship.RESIDENT: cfg.REGISTRATION_RESIDENT_ROLE_ID,
        Citizenship.PRIMARY_CITIZEN: cfg.REGISTRATION_CITIZEN_ROLE_ID,
        Citizenship.SECONDARY_CITIZEN: cfg.REGISTRATION_CITIZEN_ROLE_ID,
        "member": cfg.REGISTRATION_MEMBER_ROLE_ID,
    }


async def sync_citizen_member(
    bot: commands.Bot,
    user_id: int | None,
    citizen: Citizen | None,
    *,
    log: logging.Logger,
) -> None:
    if user_id is None:
        return

    member = await get_member(bot, user_id)
    if member is None:
        return

    if citizen is not None:
        try:
            await member.edit(nick=citizen.in_game_name)
        except Exception:  # Some Discord HTTP failures are not consistently typed here.
            log.exception("Failed to edit nickname after citizen change: %s", citizen.id)

    try:
        await sync_citizenship_roles(
            member,
            await citizenship_role_ids(bot.db),
            citizen.citizenship if citizen else None,
        )
    except Exception:  # Some Discord HTTP failures are not consistently typed here.
        log.exception("Failed to update roles after citizen change: %s", user_id)


async def sync_citizenship_roles(
    member: Member,
    role_ids: dict[Citizenship | str, int | None],
    citizenship: Citizenship | None,
) -> None:
    managed_role_ids = {role_id for role_id in role_ids.values() if role_id is not None}
    desired_role_ids = desired_citizenship_role_ids(role_ids, citizenship)

    roles_to_add = [
        role
        for role_id in desired_role_ids
        if (role := member.guild.get_role(role_id)) is not None and role not in member.roles
    ]
    roles_to_remove = [role for role in member.roles if role.id in managed_role_ids and role.id not in desired_role_ids]

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


def desired_citizenship_role_ids(
    role_ids: dict[Citizenship | str, int | None],
    citizenship: Citizenship | None,
) -> set[int]:
    if citizenship is None:
        return set()

    return {
        role_ids["member"],
        role_ids.get(citizenship),
    } - {None}

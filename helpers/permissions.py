from discord import Member
from discord.ext import commands

from helpers.citizens import ign_from_user
from helpers.discord import get_guild, get_member
from models.ShownException import BadRequestException, NotFoundException
from ui.panels.permission_list import permission_list_members, permission_list_namelayers


async def role_context_for_user(bot: commands.Bot, ign: str) -> dict[int, str]:
    citizen = await bot.db.citizens.fetch_by_ign(ign)
    if citizen is None or citizen.user_id is None:
        return {}

    member = await get_member(bot, citizen.user_id)
    if member is None:
        return {}

    return {role.id: role.mention for role in member.roles}


async def role_context_for_namelayer(
    bot: commands.Bot,
    namelayer: str,
) -> tuple[dict[int, list[str]], dict[int, str]]:
    group_permissions = [gp for gp in await bot.db.group_permissions.fetch_all() if gp.namelayer == namelayer]
    people = await bot.db.citizens.fetch_all()
    ign_by_user_id = {person.user_id: person.in_game_name for person in people if person.user_id is not None}
    if not ign_by_user_id:
        return {}, {}

    guild = await get_guild(bot)
    members = await guild.query_members(
        user_ids=list(ign_by_user_id.keys()),
    )
    role_member_igns_by_id: dict[int, list[str]] = {}
    role_sources_by_id: dict[int, str] = {}

    for gp in group_permissions:
        role = guild.get_role(gp.role_id)
        if role is None:
            continue

        role_sources_by_id[role.id] = role.mention
        role_member_igns_by_id[role.id] = [
            ign_by_user_id[member.id]
            for member in members
            if member.id in ign_by_user_id and any(member_role.id == role.id for member_role in member.roles)
        ]

    return role_member_igns_by_id, role_sources_by_id


async def resolve_permission_target(
    bot: commands.Bot,
    *,
    ign: str | None = None,
    user: Member | None = None,
) -> tuple[str, str]:
    if ign is None:
        if user is None:
            raise BadRequestException("Must pass either a role, ign or citizen.")

        ign = await ign_from_user(bot, user)

    return ign, user.mention if user else ign


async def corrected_namelayer(bot: commands.Bot, namelayer: str) -> str:
    corrected = await bot.db.group_permissions.correct_namelayer(namelayer)
    if corrected is None:
        raise NotFoundException(f"Couldn't find namelayer: {namelayer}!")
    return corrected


async def user_permission_state(bot: commands.Bot, ign: str):
    actual = await bot.db.permissions.fetch_by_ign(ign)
    target = await bot.permission_service.get_user_permissions(
        ign,
        await role_context_for_user(bot, ign),
    )
    return actual, target


async def namelayer_permission_state(bot: commands.Bot, namelayer: str):
    actual = await bot.db.permissions.fetch_by_namelayer(namelayer)
    role_member_igns_by_id, role_sources_by_id = await role_context_for_namelayer(
        bot,
        namelayer,
    )
    target = await bot.permission_service.get_namelayer_members(
        namelayer,
        role_member_igns_by_id,
        role_sources_by_id,
    )
    return actual, target


async def user_permission_panel(bot: commands.Bot, ign: str, name: str) -> dict[str, object]:
    actual, target = await user_permission_state(bot, ign)
    return permission_list_namelayers(actual, target, name)


async def namelayer_permission_panel(bot: commands.Bot, namelayer: str) -> dict[str, object]:
    actual, target = await namelayer_permission_state(bot, namelayer)
    return permission_list_members(actual, target, namelayer)

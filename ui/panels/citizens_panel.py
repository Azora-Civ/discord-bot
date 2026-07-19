from datetime import UTC, datetime

import discord

from models.citizen import Citizen
from ui.views.paginated_view import PaginationView

PAGE_SIZE = 15


def citizen_list_panel(
    citizens: list[Citizen],
    *,
    ign_filter: str | None = None,
    last_online_days: int | None = None,
    author_id: int | None = None,
) -> dict[str, object]:
    if not citizens:
        embed = discord.Embed(
            title="Citizens",
            description="No citizens found.",
            color=discord.Color.gold(),
        )
        footer = _filter_footer(
            ign_filter=ign_filter,
            last_online_days=last_online_days,
        )
        if footer:
            embed.set_footer(text=footer)
        return {"embed": embed}

    pages = []
    for index in range(0, len(citizens), PAGE_SIZE):
        chunk = citizens[index : index + PAGE_SIZE]
        lines = [_citizen_line(citizen) for citizen in chunk]
        embed = discord.Embed(
            title="Citizens",
            description="\n".join(lines),
            color=discord.Color.gold(),
        )
        embed.set_footer(
            text=_footer(
                total=len(citizens),
                page=(index // PAGE_SIZE) + 1,
                pages=((len(citizens) - 1) // PAGE_SIZE) + 1,
                ign_filter=ign_filter,
                last_online_days=last_online_days,
            )
        )
        pages.append(embed)

    if len(pages) == 1:
        return {"embed": pages[0]}

    view = PaginationView(pages, author_id=author_id)
    return {"embed": pages[0], "view": view}


def citizen_panel(citizen: Citizen) -> discord.Embed:
    embed = discord.Embed(
        title=citizen.in_game_name,
        color=discord.Color.gold(),
    )
    embed.add_field(name="Citizenship", value=citizen.citizenship.value, inline=True)
    embed.add_field(name="Discord", value=_discord_value(citizen), inline=True)
    embed.add_field(name="Joined", value=_time_value(citizen.joined_at), inline=True)
    embed.add_field(name="Last Online", value=_time_value(citizen.last_online), inline=True)
    if citizen.id is not None:
        embed.set_footer(text=f"Citizen ID: {citizen.id}")
    return embed


def citizen_stats_panel(total: int, active: int, active_days: int) -> discord.Embed:
    inactive = total - active
    embed = discord.Embed(
        title="Citizen Stats",
        color=discord.Color.gold(),
    )
    embed.add_field(name="Citizens", value=str(total), inline=True)
    embed.add_field(name=f"Active ({active_days}d)", value=str(active), inline=True)
    embed.add_field(name="Inactive", value=str(inactive), inline=True)
    return embed


def _citizen_line(citizen: Citizen) -> str:
    discord_name = _discord_value(citizen)
    return (
        f"**{citizen.in_game_name}** - {citizen.citizenship.value} - "
        f"{discord_name} - last online {_relative_time(citizen.last_online)}"
    )


def _discord_value(citizen: Citizen) -> str:
    if citizen.user_id is None:
        return "Unlinked"
    return f"<@{citizen.user_id}>"


def _time_value(value: datetime) -> str:
    timestamp = int(_aware(value).timestamp())
    return f"<t:{timestamp}:F>\n<t:{timestamp}:R>"


def _relative_time(value: datetime) -> str:
    return f"<t:{int(_aware(value).timestamp())}:R>"


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value


def _footer(
    *,
    total: int,
    page: int,
    pages: int,
    ign_filter: str | None,
    last_online_days: int | None,
) -> str:
    text = f"{total} result(s) - Page {page}/{pages}"
    footer = _filter_footer(
        ign_filter=ign_filter,
        last_online_days=last_online_days,
    )
    if footer:
        text += f" - {footer}"
    return text


def _filter_footer(
    *,
    ign_filter: str | None,
    last_online_days: int | None,
) -> str:
    filters = []
    if ign_filter:
        filters.append(f"IGN: {ign_filter}")
    if last_online_days is not None:
        filters.append(f"Last online: {last_online_days}d")
    return " | ".join(filters)

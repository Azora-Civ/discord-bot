import time

import discord

from models.farm import Farm, FarmState


def farm_embed(farm: Farm) -> discord.Embed:
    state, ready_at = _farm_state(farm)

    lines = [
        f"📍 **Location:** `{farm.posxyz}`",
        "",
        f"🌱 **Status:** {_format_state(state, ready_at)}",
    ]

    if last_farmed_by := farm.additional_data.get("last_farmed_by"):
        lines.append(f"🧑‍🌾 **Last farmed by:** {last_farmed_by}")

    lines.extend(
        [
            "",
            "⏱️ **Farm Details**",
            f"**Regrow time:** {_format_interval(farm.regrow_time)}",
            f"**Time to farm:** {_format_interval(farm.farm_time)}",
            "",
            "📜 **Latest Run**",
            f"**Started:** {_format_timestamp(farm.started_time)}",
            f"**Finished:** {_format_timestamp(farm.finished_time)}",
        ]
    )

    return discord.Embed(
        title=f"🌾 {farm.name}",
        description="\n".join(lines),
        color=_state_color(state),
        timestamp=discord.utils.utcnow(),
    )

async def panel_embed(bot) -> discord.Embed:
    farms = await bot.db.farms.fetch_all()
    embed = discord.Embed(
        title="Live Farm Updates",
        color=discord.Color.green(),
        timestamp=discord.utils.utcnow(),
    )

    if not farms:
        embed.description = "No farms configured."
        return embed

    farms = sorted(farms, key=lambda farm: farm.name, reverse=True)

    lines = [_panel_line(farm) for farm in farms]
    embed.description = "\n".join(lines)
    embed.set_footer(
        text=f"{len(farms)} farm(s) tracked"
    )
    return embed

def _format_state(state, ready_at) -> str | None:
    if state == FarmState.UNKNOWN:
        return "❓ Unknown"
    elif state == FarmState.GROWING:
        return f"⌛ Growing (ready {_format_timestamp(ready_at)})"
    elif state == FarmState.BEING_FARMED:
        return f"⚒️ Being Farmed (ready {_format_timestamp(ready_at)})"
    if state == FarmState.FULLY_GROWN:
        return "✅ Ready"

    return None

def _panel_line(farm: Farm) -> str:
    state, ready_at = _farm_state(farm)
    return f"**{farm.name}:** {_format_state(state, ready_at)}"

def _farm_state(farm: Farm) -> tuple[FarmState, int | None]:
    now = int(time.time())

    if farm.started_time is None and farm.finished_time is None:
        return FarmState.UNKNOWN, None

    # not yet or never finished
    if farm.started_time is not None and (
        farm.finished_time is None or farm.started_time > farm.finished_time
    ):
        # estimate times generously
        finished_at = farm.started_time + (2 * farm.farm_time)
        ready_at = finished_at + farm.regrow_time

        if finished_at > now:
            return FarmState.BEING_FARMED, ready_at
        if ready_at < now:
            return FarmState.FULLY_GROWN, ready_at
        return FarmState.GROWING, ready_at

    if farm.finished_time is not None:
        ready_at = farm.finished_time + farm.regrow_time

        if ready_at < now:
            return FarmState.FULLY_GROWN, ready_at
        return FarmState.GROWING, ready_at

    return FarmState.UNKNOWN, None

def _state_color(state: FarmState) -> discord.Color:
    if state == FarmState.FULLY_GROWN:
        return discord.Color.green()
    if state == FarmState.GROWING:
        return discord.Color.gold()
    return discord.Color.light_grey()


def _format_timestamp(value: int | None) -> str:
    if value is None:
        return "Unknown"
    return f"<t:{value}:R>"


def _format_interval(seconds: int) -> str:
    hours, remainder = divmod(seconds, 60 * 60)
    minutes = remainder // 60
    parts = []
    if hours:
        parts.append(f"{hours}h")
    if minutes:
        parts.append(f"{minutes}m")
    return " ".join(parts) or "0m"

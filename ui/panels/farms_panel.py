import re
import time

import discord

from models.farm import Farm, FarmState

FARM_LAYER_REGEX = re.compile(r"^(?P<base>.+?)\s+L(?P<layer>\d+)$", re.IGNORECASE)


def farm_embed(farm: Farm) -> discord.Embed:
    state, ready_at = _farm_state(farm)

    lines = [
        f"📍 **Location:** `{farm.posxyz}`",
        "",
        f"🌱 **Status:** {_format_state(state, ready_at)}",
    ]

    if last_farmed_by := farm.additional_data.get("last_farmed_by"):
        lines.append(f"🧑‍🌾 **Last farmed by:** {last_farmed_by}")

    if requirements := farm.additional_data.get("requirements"):
        lines.extend(["", f"**Requirements:** {requirements}"])

    if info := farm.additional_data.get("info"):
        lines.extend(["", f"**Info:** {info}"])

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

    farms = sorted(farms, key=lambda farm: farm.name)

    for name, value in _panel_fields(farms):
        embed.add_field(name=name, value=value, inline=True)

    embed.set_footer(
        text=f"{len(farms)} farm(s) tracked"
    )
    return embed

def _format_state(state, ready_at) -> str | None:
    if state == FarmState.UNKNOWN:
        return "❓ Unknown"
    elif state == FarmState.GROWING:
        return f"⌛ {_format_timestamp(ready_at)}"
    elif state == FarmState.BEING_FARMED:
        return "⚒️ In Use"
    if state == FarmState.FULLY_GROWN:
        return "✅ Ready"

    return None

def _panel_fields(farms: list[Farm]) -> list[tuple[str, str]]:
    farm_groups: dict[str, list[tuple[int, Farm]]] = {}
    unlayered_farms: list[Farm] = []

    for farm in farms:
        base_name, layer = _farm_layer(farm.name)
        if layer is None:
            farm_groups.setdefault(base_name, []).append((1, farm))
        else:
            farm_groups.setdefault(base_name, []).append((layer, farm))

    for farm in farms:
        base_name, layer = _farm_layer(farm.name)
        if layer is None and len(farm_groups[base_name]) == 1:
            unlayered_farms.append(farm)

    fields: list[tuple[str, str]] = []
    emitted_groups: set[str] = set()
    unlayered_names = {farm.name for farm in unlayered_farms}
    for farm in farms:
        if farm.name in unlayered_names:
            fields.append((farm.name, _panel_field_value(farm)))
            continue

        base_name, _ = _farm_layer(farm.name)
        if base_name in emitted_groups:
            continue

        emitted_groups.add(base_name)
        fields.append((base_name, _layered_panel_field_value(farm_groups[base_name])))

    return fields


def _farm_layer(name: str) -> tuple[str, int | None]:
    if match := FARM_LAYER_REGEX.match(name.strip()):
        return match.group("base").strip(), int(match.group("layer"))

    return name, None


def _panel_field_value(farm: Farm) -> str:
    state, ready_at = _farm_state(farm)
    return _format_state(state, ready_at) or "Unknown"


def _layered_panel_field_value(farms: list[tuple[int, Farm]]) -> str:
    ordered_farms = sorted(farms, key=lambda item: item[0])
    layer_states = [(layer, *_farm_state(farm)) for layer, farm in ordered_farms]

    if all(state == FarmState.FULLY_GROWN for _, state, _ in layer_states):
        return _format_state(FarmState.FULLY_GROWN, None) or "Ready"

    layer_display_states = [
        (layer, _format_state(state, ready_at))
        for layer, state, ready_at in layer_states
    ]
    parts = [
        f"{_format_layer_range(start, end)}: {display_state}"
        for start, end, display_state in _combine_layer_states(layer_display_states)
    ]
    return "\n".join(parts)


def _combine_layer_states(
    layer_states: list[tuple[int, str | None]],
) -> list[tuple[int, int, str | None]]:
    combined: list[tuple[int, int, str | None]] = []

    for layer, display_state in layer_states:
        if not combined:
            combined.append((layer, layer, display_state))
            continue

        start, end, previous_display_state = combined[-1]
        if layer == end + 1 and display_state == previous_display_state:
            combined[-1] = (start, layer, display_state)
            continue

        combined.append((layer, layer, display_state))

    return combined


def _format_layer_range(start: int, end: int) -> str:
    if start == end:
        return f"L{start}"

    return f"L{start}-L{end}"

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

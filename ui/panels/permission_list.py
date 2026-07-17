from collections.abc import Callable

import discord

from models.permission import Permission, PermissionLevel
from ui.panels.paginated_panel import paginated_panel

MAX_EMBED_LENGTH = 5900
MAX_FIELD_COUNT = 25
MAX_FIELD_VALUE_LENGTH = 1024

PREFIX_MATCH = " "
PREFIX_GIVE = "🟩"
PREFIX_REMOVE = "🟥"


def permission_list_members(
        actual: list[Permission],
        target: list[Permission],
        namelayer: str,
) -> dict[str, object]:
    return _permission_list(
        actual=actual,
        target=target,
        title=f"Member permissions for {namelayer}",
        empty_description="No members found.",
        key=lambda permission: permission.ign,
    )


def permission_list_namelayers(
        actual: list[Permission],
        target: list[Permission],
        name: str,
) -> dict[str, object]:
    return _permission_list(
        actual=actual,
        target=target,
        title=f"Namelayer permissions for {name}",
        empty_description="No namelayers found.",
        key=lambda permission: permission.namelayer,
    )


def _permission_list(
        actual: list[Permission],
        target: list[Permission],
        title: str,
        empty_description: str,
        key: Callable[[Permission], str],
) -> dict[str, object]:
    target_by_key = {key(permission): permission for permission in target}
    actual_by_key = {key(permission): permission for permission in actual}

    entries: list[tuple[PermissionLevel, str, str, int]] = []
    for permission_key in sorted(target_by_key.keys() | actual_by_key.keys()):
        target_permission = target_by_key.get(permission_key)
        actual_permission = actual_by_key.get(permission_key)

        if target_permission and actual_permission and _permission_matches(
                target_permission.level,
                actual_permission.level,
        ):
            entries.append(
                _permission_entry(
                    target_permission.level,
                    PREFIX_MATCH,
                    permission_key,
                    target_permission,
                )
            )
            continue

        if actual_permission:
            entries.append(
                _permission_entry(
                    actual_permission.level,
                    PREFIX_REMOVE,
                    permission_key,
                    None,
                )
            )

        if target_permission:
            entries.append(
                _permission_entry(
                    target_permission.level,
                    PREFIX_GIVE,
                    permission_key,
                    target_permission,
                )
            )

    fields = _grouped_fields(entries)

    if not fields:
        return paginated_panel([
            discord.Embed(
                title=title,
                description=empty_description,
                color=discord.Color.blurple(),
            )
        ])

    chunks = _chunk_fields(fields)
    total = len(chunks)

    embeds: list[discord.Embed] = []
    for index, chunk in enumerate(chunks, start=1):
        embed = discord.Embed(
            title=(
                f"{title} ({index}/{total})"
                if total > 1
                else title
            ),
            description=f"{PREFIX_REMOVE} -> remove | {PREFIX_GIVE} -> add",
            color=discord.Color.blurple(),
        )
        for name, value in chunk:
            embed.add_field(name=name, value=value, inline=True)
        embeds.append(embed)

    return paginated_panel(embeds)


def _permission_matches(
        target_level: PermissionLevel,
        actual_level: PermissionLevel,
) -> bool:
    if target_level == actual_level:
        return True

    owner_levels = {
        PermissionLevel.PRIMARY_OWNER,
        PermissionLevel.OWNER,
    }

    return target_level in owner_levels and actual_level in owner_levels


def _permission_entry(
        level: PermissionLevel,
        prefix: str,
        permission_key: str,
        target_permission: Permission | None,
) -> tuple[PermissionLevel, str, str, int]:
    return (
        level,
        permission_key,
        _permission_line(prefix, permission_key, target_permission),
        _prefix_sort_key(prefix),
    )


def _permission_line(
        prefix: str,
        permission_key: str,
        target_permission: Permission | None,
) -> str:
    line = f"{prefix} {discord.utils.escape_markdown(permission_key)}"

    source = getattr(target_permission, "source", None)
    if source:
        line += f" ({source})"

    return line


def _grouped_fields(
        entries: list[tuple[PermissionLevel, str, str, int]],
) -> list[tuple[str, str]]:
    fields: list[tuple[str, str]] = []

    for level in sorted(
            {entry[0] for entry in entries},
            key=lambda level: level.value,
            reverse=True,
    ):
        level_entries = [
            entry
            for entry in entries
            if entry[0] == level
        ]
        lines = [
            line
            for _, _, line, _ in sorted(
                level_entries,
                key=lambda entry: (entry[1].casefold(), entry[3]),
            )
        ]

        for field_value in _field_values(lines):
            fields.append((level.name, field_value))

    return fields


def _prefix_sort_key(prefix: str) -> int:
    if prefix == PREFIX_GIVE:
        return 0

    if prefix == PREFIX_REMOVE:
        return 1

    return 2


def _field_values(lines: list[str]) -> list[str]:
    values: list[str] = []
    current_lines: list[str] = []
    current_length = _format_length([])

    for line in lines:
        line_length = len(line) + 1

        if current_lines and current_length + line_length > MAX_FIELD_VALUE_LENGTH:
            values.append(_format(current_lines))
            current_lines = []
            current_length = _format_length([])

        current_lines.append(line)
        current_length += line_length

    if current_lines:
        values.append(_format(current_lines))

    return values


def _chunk_fields(fields: list[tuple[str, str]]) -> list[list[tuple[str, str]]]:
    chunks: list[list[tuple[str, str]]] = []
    current_chunk: list[tuple[str, str]] = []
    current_length = 0

    for field in fields:
        field_length = len(field[0]) + len(field[1])

        if current_chunk and (
                len(current_chunk) >= MAX_FIELD_COUNT
                or current_length + field_length > MAX_EMBED_LENGTH
        ):
            chunks.append(current_chunk)
            current_chunk = []
            current_length = 0

        current_chunk.append(field)
        current_length += field_length

    if current_chunk:
        chunks.append(current_chunk)

    return chunks


def _format(lines: list[str]) -> str:
    return "\n".join(lines)


def _format_length(lines: list[str]) -> int:
    return len(_format(lines))

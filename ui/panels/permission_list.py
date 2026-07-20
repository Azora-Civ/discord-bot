from collections.abc import Callable

import discord

from models.permission import Permission, PermissionLevel
from ui.panels.paginated_panel import paginated_panel

FIELDS_PER_EMBED = 2
MAX_FIELD_TOTAL_LINES = 40
MAX_FIELD_VALUE_LINES = MAX_FIELD_TOTAL_LINES - 1
MAX_FIELD_VALUE_LENGTH = 1024
MAX_BALANCED_ENTRY_COUNT = MAX_FIELD_TOTAL_LINES * FIELDS_PER_EMBED

PREFIX_MATCH = " "
PREFIX_GIVE = "🟩"
PREFIX_REMOVE = "🟥"

ACTION_REMOVE = 0
ACTION_KEEP = 1
ACTION_ADD = 2

PermissionEntry = tuple[PermissionLevel, int, str, str]


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

    entries: list[PermissionEntry] = []
    for permission_key in sorted(target_by_key.keys() | actual_by_key.keys()):
        target_permission = target_by_key.get(permission_key)
        actual_permission = actual_by_key.get(permission_key)

        if (
            target_permission
            and actual_permission
            and _permission_matches(
                target_permission.level,
                actual_permission.level,
            )
        ):
            entries.append(
                _permission_entry(
                    target_permission.level,
                    PREFIX_MATCH,
                    permission_key,
                    target_permission,
                    ACTION_KEEP,
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
                    ACTION_REMOVE,
                )
            )

        if target_permission:
            entries.append(
                _permission_entry(
                    target_permission.level,
                    PREFIX_GIVE,
                    permission_key,
                    target_permission,
                    ACTION_ADD,
                )
            )

    fields = _fields(_sorted_entries(entries))

    if not fields:
        return paginated_panel(
            [
                discord.Embed(
                    title=title,
                    description=empty_description,
                    color=discord.Color.blurple(),
                )
            ]
        )

    pages = _chunk_fields(fields)
    total = len(pages)

    embeds: list[discord.Embed] = []
    for index, page in enumerate(pages, start=1):
        embed = discord.Embed(
            title=(f"{title} ({index}/{total})" if total > 1 else title),
            description=f"{PREFIX_REMOVE} -> remove | {PREFIX_GIVE} -> add",
            color=discord.Color.blurple(),
        )
        for name, value in page:
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
    action: int,
) -> PermissionEntry:
    return (
        level,
        action,
        permission_key,
        _permission_line(prefix, permission_key, target_permission),
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


def _sorted_entries(entries: list[PermissionEntry]) -> list[PermissionEntry]:
    return sorted(
        entries,
        key=lambda entry: (
            -entry[0].value,
            entry[1],
            entry[2].casefold(),
        ),
    )


def _fields(entries: list[PermissionEntry]) -> list[tuple[str, str]]:
    if len(entries) <= MAX_BALANCED_ENTRY_COUNT:
        balanced_chunks = _balanced_chunks(entries)
        if balanced_chunks is not None:
            return [_field(chunk) for chunk in balanced_chunks]

    return [_field(chunk) for chunk in _entry_chunks(entries)]


def _balanced_chunks(entries: list[PermissionEntry]) -> list[list[PermissionEntry]] | None:
    if len(entries) <= 1 and _valid_field(entries):
        return [entries]

    best_chunks = None
    best_delta = None
    for split_index in range(1, len(entries)):
        chunks = [entries[:split_index], entries[split_index:]]
        if not all(_valid_field(chunk) for chunk in chunks):
            continue

        delta = abs(_field_line_count(chunks[0]) - _field_line_count(chunks[1]))
        if best_delta is None or delta < best_delta:
            best_chunks = chunks
            best_delta = delta

    if best_chunks is None:
        return None

    return best_chunks


def _entry_chunks(entries: list[PermissionEntry]) -> list[list[PermissionEntry]]:
    chunks: list[list[PermissionEntry]] = []
    current_chunk: list[PermissionEntry] = []

    for entry in entries:
        next_chunk = [*current_chunk, entry]
        if current_chunk and not _valid_field(next_chunk):
            chunks.append(current_chunk)
            current_chunk = [entry]
            continue

        current_chunk = next_chunk

    if current_chunk:
        chunks.append(current_chunk)

    return _balance_last_chunks(chunks)


def _balance_last_chunks(chunks: list[list[PermissionEntry]]) -> list[list[PermissionEntry]]:
    if len(chunks) < 2 or len(chunks) % FIELDS_PER_EMBED == 0:
        return chunks

    last_entries = chunks.pop()
    previous_entries = chunks.pop()
    balanced_chunks = _balanced_chunks(previous_entries + last_entries)
    if balanced_chunks is None:
        chunks.extend([previous_entries, last_entries])
        return chunks

    chunks.extend(balanced_chunks)
    return chunks


def _valid_field(entries: list[PermissionEntry]) -> bool:
    if not entries:
        return False

    return _field_line_count(entries) <= MAX_FIELD_VALUE_LINES and len(_field_value(entries)) <= MAX_FIELD_VALUE_LENGTH


def _field_line_count(entries: list[PermissionEntry]) -> int:
    lines = 0
    current_level: PermissionLevel | None = None
    for entry in entries:
        lines += _additional_line_count_for_level(current_level, entry[0])
        current_level = entry[0]

    return lines


def _additional_line_count_for_level(
    current_level: PermissionLevel | None,
    next_level: PermissionLevel,
) -> int:
    if current_level in {None, next_level}:
        return 1

    return 2


def _field(entries: list[PermissionEntry]) -> tuple[str, str]:
    return entries[0][0].name, _field_value(entries)


def _field_value(entries: list[PermissionEntry]) -> str:
    lines: list[str] = []
    current_level = entries[0][0]

    for level, _, _, line in entries:
        if level != current_level:
            lines.append(f"**{level.name}**")
            current_level = level

        lines.append(line)

    return _format(lines)


def _chunk_fields(fields: list[tuple[str, str]]) -> list[list[tuple[str, str]]]:
    return [fields[index : index + FIELDS_PER_EMBED] for index in range(0, len(fields), FIELDS_PER_EMBED)]


def _format(lines: list[str]) -> str:
    return "\n".join(lines)

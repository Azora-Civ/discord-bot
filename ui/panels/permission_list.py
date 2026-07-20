from collections.abc import Callable, Sequence

import discord

from models.permission import Permission, PermissionLevel
from ui.panels.paginated_panel import paginated_panel


FIELDS_PER_EMBED = 2

MAX_FIELD_TOTAL_LINES = 40
MAX_FIELD_VALUE_LINES = MAX_FIELD_TOTAL_LINES - 1
MAX_FIELD_VALUE_LENGTH = 1024
MAX_FIELD_NAME_LENGTH = 256

PREFIX_MATCH = " "
PREFIX_GIVE = "🟩"
PREFIX_REMOVE = "🟥"

PREFIX_TO_SORT_KEY = {
    PREFIX_REMOVE: 0,
    PREFIX_MATCH: 1,
    PREFIX_GIVE: 2,
}


PermissionEntry = tuple[PermissionLevel, int, str, str]
"""
(permission level, action, key, rendered line)
"""

PermissionSection = list[PermissionEntry]


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
    entries = _sorted_entries(_to_entries(actual, target, key))
    sections = _split(entries)

    if not sections:
        return paginated_panel(
            [
                discord.Embed(
                    title=title,
                    description=empty_description,
                    color=discord.Color.blurple(),
                )
            ]
        )

    pages = _to_pages(sections)
    total = len(pages)

    embeds: list[discord.Embed] = []

    for index, page in enumerate(pages, start=1):
        embed = discord.Embed(
            title=f"{title} ({index}/{total})" if total > 1 else title,
            description=f"{PREFIX_REMOVE} → remove | {PREFIX_GIVE} → add",
            color=discord.Color.blurple(),
        )

        for section in page:
            embed.add_field(
                name=_to_field_name(section),
                value=_to_field_value(section),
                inline=len(page) > 1,
            )

        embeds.append(embed)

    return paginated_panel(embeds)


def _to_entries(
    actual: list[Permission],
    target: list[Permission],
    key: Callable[[Permission], str],
) -> list[PermissionEntry]:
    actual_by_key = _index_permissions(actual, key)
    target_by_key = _index_permissions(target, key)

    entries: list[PermissionEntry] = []

    for normalized_key in sorted(actual_by_key.keys() | target_by_key.keys()):
        actual_item = actual_by_key.get(normalized_key)
        target_item = target_by_key.get(normalized_key)

        actual_permission = actual_item[1] if actual_item else None
        target_permission = target_item[1] if target_item else None

        # Prefer the target's casing when both sides contain the key.
        permission_key = (
            target_item[0]
            if target_item is not None
            else actual_item[0]  # type: ignore[index]
        )

        if (
            target_permission is not None
            and actual_permission is not None
            and permission_matches(
                target_permission.level,
                actual_permission.level,
            )
        ):
            entries.append(
                _to_entry(
                    PREFIX_MATCH,
                    permission_key,
                    target_permission,
                )
            )
            continue

        if actual_permission is not None:
            entries.append(
                _to_entry(
                    PREFIX_REMOVE,
                    permission_key,
                    actual_permission,
                )
            )

        if target_permission is not None:
            entries.append(
                _to_entry(
                    PREFIX_GIVE,
                    permission_key,
                    target_permission,
                )
            )

    return entries


def _index_permissions(
    permissions: Sequence[Permission],
    key: Callable[[Permission], str],
) -> dict[str, tuple[str, Permission]]:
    result: dict[str, tuple[str, Permission]] = {}

    for permission in permissions:
        permission_key = key(permission)
        normalized_key = permission_key.casefold()

        if normalized_key in result:
            raise ValueError(
                f"Duplicate permission key: {permission_key!r}"
            )

        result[normalized_key] = permission_key, permission

    return result


def _to_entry(
    prefix: str,
    permission_key: str,
    permission: Permission,
) -> PermissionEntry:
    line = f"{prefix} {_escape_display_text(permission_key)}"

    source = getattr(permission, "source", None)
    if source is not None:
        line += f" ({_escape_display_text(source)})"

    return (
        permission.level,
        PREFIX_TO_SORT_KEY[prefix],
        permission_key,
        _truncate(line, MAX_FIELD_VALUE_LENGTH),
    )


def _sorted_entries(
    entries: Sequence[PermissionEntry],
) -> list[PermissionEntry]:
    return sorted(
        entries,
        key=lambda entry: (
            -entry[0].value,
            entry[1],
            entry[2].casefold(),
        ),
    )


def _split(
    entries: Sequence[PermissionEntry],
) -> list[PermissionSection]:
    sections: list[PermissionSection] = []
    current: PermissionSection = []

    for entry in entries:
        candidate = [*current, entry]

        if current and not _field_fits(candidate):
            sections.append(current)
            current = [entry]
        else:
            current = candidate

        # This should only be possible when one rendered line itself is invalid.
        if not _field_fits(current):
            raise ValueError(
                f"Permission entry cannot fit in a Discord field: {entry[2]!r}"
            )

    if current:
        sections.append(current)

    return sections


def _to_pages(
    sections: Sequence[PermissionSection],
) -> list[list[PermissionSection]]:
    pages: list[list[PermissionSection]] = []

    for index in range(0, len(sections), FIELDS_PER_EMBED):
        page = list(sections[index : index + FIELDS_PER_EMBED])

        if FIELDS_PER_EMBED == 2:
            left = page[0]
            right = page[1] if len(page) > 1 else []

            left, right = _balance(left, right)
            page = [section for section in (left, right) if section]

        pages.append(page)

    return pages


def _balance(
    left: PermissionSection,
    right: PermissionSection,
) -> tuple[PermissionSection, PermissionSection]:
    combined = [*left, *right]

    if len(combined) < 2:
        return left, right

    candidates: list[
        tuple[
            tuple[int, int],
            PermissionSection,
            PermissionSection,
        ]
    ] = []

    for split_index in range(1, len(combined)):
        candidate_left = combined[:split_index]
        candidate_right = combined[split_index:]

        if not (
            _field_fits(candidate_left)
            and _field_fits(candidate_right)
        ):
            continue

        score = (
            abs(
                _field_value_line_count(candidate_left)
                - _field_value_line_count(candidate_right)
            ),
            abs(len(candidate_left) - len(candidate_right)),
        )

        candidates.append(
            (score, candidate_left, candidate_right)
        )

    if not candidates:
        return left, right

    _, balanced_left, balanced_right = min(
        candidates,
        key=lambda candidate: candidate[0],
    )

    return balanced_left, balanced_right


def _field_fits(entries: Sequence[PermissionEntry]) -> bool:
    if not entries:
        return False

    return (
        _field_value_line_count(entries) <= MAX_FIELD_VALUE_LINES
        and len(_to_field_value(entries)) <= MAX_FIELD_VALUE_LENGTH
    )


def _field_value_line_count(
    entries: Sequence[PermissionEntry],
) -> int:
    if not entries:
        return 0

    level_headings = sum(
        previous[0] != current[0]
        for previous, current in zip(entries, entries[1:])
    )

    return len(entries) + level_headings


def _to_field_name(
    entries: Sequence[PermissionEntry],
) -> str:
    return _truncate(entries[0][0].name, MAX_FIELD_NAME_LENGTH)


def _to_field_value(
    entries: Sequence[PermissionEntry],
) -> str:
    lines: list[str] = []
    current_level = entries[0][0]

    for entry in entries:
        level = entry[0]

        if level != current_level:
            current_level = level
            lines.append(f"**{level.name}**")

        lines.append(entry[3])

    return "\n".join(lines)


def _escape_display_text(value: object) -> str:
    text = str(value).replace("\r", " ").replace("\n", " ")
    text = discord.utils.escape_markdown(text)
    return discord.utils.escape_mentions(text)


def _truncate(value: str, maximum: int) -> str:
    if len(value) <= maximum:
        return value

    truncated = value[: maximum - 1].rstrip()

    # Avoid ending on half of a Markdown escape sequence.
    truncated = truncated.rstrip("\\")

    return truncated + "…"

def permission_matches(
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
import discord

from models.permission import Permission
from models.permission_group import GroupPermission
from ui.panels.paginated_panel import paginated_panel

PAGE_SIZE = 20


def configured_permissions_panel(
    *,
    group_permissions: list[GroupPermission],
    user_permissions: list[Permission],
    role_filter: discord.Role | None = None,
    ign_filter: str | None = None,
    namelayer_filter: str | None = None,
) -> dict[str, object]:
    entries = [
        _group_permission_line(permission)
        for permission in group_permissions
        if _matches_group_permission(permission, role_filter, namelayer_filter)
    ]
    entries.extend(
        _user_permission_line(permission)
        for permission in user_permissions
        if _matches_user_permission(permission, ign_filter, namelayer_filter)
    )
    entries = sorted(entries, key=str.casefold)

    if not entries:
        embed = discord.Embed(
            title="Configured Permissions",
            description="No configured permissions found.",
            color=discord.Color.blurple(),
        )
        footer = _footer(role_filter=role_filter, ign_filter=ign_filter, namelayer_filter=namelayer_filter)
        if footer:
            embed.set_footer(text=footer)
        return {"embed": embed}

    pages = []
    page_count = ((len(entries) - 1) // PAGE_SIZE) + 1
    for index in range(0, len(entries), PAGE_SIZE):
        page = (index // PAGE_SIZE) + 1
        embed = discord.Embed(
            title="Configured Permissions",
            description="\n".join(entries[index : index + PAGE_SIZE]),
            color=discord.Color.blurple(),
        )
        footer = _footer(
            role_filter=role_filter,
            ign_filter=ign_filter,
            namelayer_filter=namelayer_filter,
            total=len(entries),
            page=page,
            page_count=page_count,
        )
        embed.set_footer(text=footer)
        pages.append(embed)

    return paginated_panel(pages)


def _group_permission_line(permission: GroupPermission) -> str:
    return f"<@&{permission.role_id}> {permission.namelayer} {permission.level.name}"


def _user_permission_line(permission: Permission) -> str:
    return f"`{permission.ign}` {permission.namelayer} {permission.level.name}"


def _matches_group_permission(
    permission: GroupPermission,
    role_filter: discord.Role | None,
    namelayer_filter: str | None,
) -> bool:
    if role_filter is not None and permission.role_id != role_filter.id:
        return False

    return _matches_namelayer(permission.namelayer, namelayer_filter)


def _matches_user_permission(
    permission: Permission,
    ign_filter: str | None,
    namelayer_filter: str | None,
) -> bool:
    if ign_filter is not None and permission.ign.casefold() != ign_filter.casefold():
        return False

    return _matches_namelayer(permission.namelayer, namelayer_filter)


def _matches_namelayer(value: str, namelayer_filter: str | None) -> bool:
    if namelayer_filter is None:
        return True

    return value.casefold() == namelayer_filter.casefold()


def _footer(
    *,
    role_filter: discord.Role | None,
    ign_filter: str | None,
    namelayer_filter: str | None,
    total: int | None = None,
    page: int | None = None,
    page_count: int | None = None,
) -> str:
    parts = []
    if total is not None and page is not None and page_count is not None:
        parts.append(f"{total} result(s) - Page {page}/{page_count}")

    filters = []
    if role_filter is not None:
        filters.append(f"Role: {role_filter.name}")
    if ign_filter is not None:
        filters.append(f"IGN: {ign_filter}")
    if namelayer_filter is not None:
        filters.append(f"Namelayer: {namelayer_filter}")

    if filters:
        parts.append(" | ".join(filters))

    return " - ".join(parts)

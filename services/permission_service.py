from typing import TYPE_CHECKING

from models.permission import Permission, PermissionLevel
from models.permission_group import GroupPermission
from services.events import ChangeKind, EventHook, GroupPermissionChangedEvent, PermissionChangedEvent

if TYPE_CHECKING:
    from database import Database


class PermissionService:
    def __init__(self, db: "Database"):
        self.db = db
        self.on_permission_changed = EventHook[PermissionChangedEvent]("on_permission_changed")
        self.on_group_permission_changed = EventHook[GroupPermissionChangedEvent]("on_group_permission_changed")

    async def update_actual_user_permission(self, permission: Permission):
        old = await self.db.permissions.find_by_ign_and_namelayer(permission.ign, permission.namelayer)
        await self._update_permission(
            old,
            permission,
            self.db.permissions,
            source="actual_permission_updated",
        )

    async def update_user_permission(self, permission: Permission):
        old = await self.db.permission_exceptions.find_by_ign_and_namelayer(permission.ign, permission.namelayer)
        await self._update_permission(
            old,
            permission,
            self.db.permission_exceptions,
            source="permission_exception_updated",
        )

    async def update_group_permission(self, permission: GroupPermission):
        old = await self.db.group_permissions.find_by_role_id_and_namelayer(
            permission.role_id,
            permission.namelayer,
        )
        kind = await _compare_and_update(
            old,
            permission,
            self.db.group_permissions,
        )
        if kind is not None:
            await self.on_group_permission_changed.emit(
                GroupPermissionChangedEvent(
                    kind=kind,
                    permission=permission,
                    previous=old,
                    source="group_permission_updated",
                )
            )

    async def _update_permission(
        self,
        old: Permission | None,
        permission: Permission,
        repo,
        *,
        source: str,
    ) -> None:
        kind = await _compare_and_update(old, permission, repo)
        if kind is None:
            return

        await self.on_permission_changed.emit(
            PermissionChangedEvent(
                kind=kind,
                permission=permission,
                previous=old,
                source=source,
            )
        )

    async def get_user_permissions(
        self,
        user_ign: str,
        role_sources_by_id: dict[int, str] | None = None,
    ) -> list[Permission]:
        role_sources_by_id = role_sources_by_id or {}
        perm_map: dict[str, Permission] = {}

        def add_permission(permission: Permission) -> None:
            current = perm_map.get(permission.namelayer)

            if current is None or permission.level.value > current.level.value:
                perm_map[permission.namelayer] = permission

        for gp in await self.db.group_permissions.fetch_all():
            source = role_sources_by_id.get(gp.role_id)
            if source is None:
                continue

            add_permission(
                Permission(
                    ign=user_ign,
                    namelayer=gp.namelayer,
                    level=gp.level,
                    source=source,
                )
            )

        for exception in await self.db.permission_exceptions.fetch_by_ign(user_ign):
            add_permission(
                Permission(
                    ign=user_ign,
                    namelayer=exception.namelayer,
                    level=exception.level,
                    source="direct",
                )
            )

        return list(perm_map.values())

    async def get_namelayer_members(
        self,
        namelayer: str,
        role_member_igns_by_id: dict[int, list[str]] | None = None,
        role_sources_by_id: dict[int, str] | None = None,
    ) -> list[Permission]:
        role_member_igns_by_id = role_member_igns_by_id or {}
        role_sources_by_id = role_sources_by_id or {}
        group_permissions = [gp for gp in await self.db.group_permissions.fetch_all() if gp.namelayer == namelayer]

        perm_map: dict[str, Permission] = {}

        def add_permission(permission: Permission) -> None:
            current = perm_map.get(permission.ign)

            if current is None or permission.level.value > current.level.value:
                perm_map[permission.ign] = permission

        for gp in group_permissions:
            source = role_sources_by_id.get(gp.role_id)
            if source is None:
                continue

            for ign in role_member_igns_by_id.get(gp.role_id, []):
                add_permission(
                    Permission(
                        ign=ign,
                        namelayer=namelayer,
                        level=gp.level,
                        source=source,
                    )
                )

        for exception in await self.db.permission_exceptions.fetch_by_namelayer(namelayer):
            add_permission(
                Permission(
                    ign=exception.ign,
                    namelayer=namelayer,
                    level=exception.level,
                    source="direct",
                )
            )

        return list(perm_map.values())

    async def get_user_permission_commands(
        self,
        user_ign: str,
        role_sources_by_id: dict[int, str] | None = None,
    ) -> list[str]:
        target_perms = await self.get_user_permissions(user_ign, role_sources_by_id)
        actual_perms = await self.db.permissions.fetch_by_ign(user_ign)

        target_by_nl = {p.namelayer: p for p in target_perms}
        actual_by_nl = {p.namelayer: p for p in actual_perms}

        return await _to_commands(target_by_nl, actual_by_nl)

    async def get_namelayer_member_commands(
        self,
        namelayer: str,
        role_member_igns_by_id: dict[int, list[str]] | None = None,
        role_sources_by_id: dict[int, str] | None = None,
    ) -> list[str]:
        target_perms = await self.get_namelayer_members(
            namelayer,
            role_member_igns_by_id,
            role_sources_by_id,
        )
        actual_perms = await self.db.permissions.fetch_by_namelayer(namelayer)

        target_by_ign = {p.ign: p for p in target_perms}
        actual_by_ign = {p.ign: p for p in actual_perms}

        return await _to_commands(target_by_ign, actual_by_ign)

    async def import_permissions(self, entries: list[Permission]):
        namelayers = list({entry.namelayer for entry in entries})
        await self.db.permissions.delete_by_namelayers(namelayers)
        await self.db.permissions.batch_create(entries)


async def _to_commands(targets: dict[str, Permission], actuals: dict[str, Permission]):
    commands: list[str] = []
    all_keys = targets.keys() | actuals.keys()

    for key in sorted(all_keys):
        target = targets.get(key)
        actual = actuals.get(key)

        target_level = target.level if target else PermissionLevel.DEFAULT
        actual_level = actual.level if actual else PermissionLevel.DEFAULT

        cmd = await _to_command(target or actual, actual_level, target_level)
        if cmd:
            commands.append(cmd)

    return commands


async def _to_command(perm: Permission, actual_level: PermissionLevel, target_level: PermissionLevel) -> str | None:
    if target_level == actual_level:
        return None

    owner_levels = {
        PermissionLevel.PRIMARY_OWNER,
        PermissionLevel.OWNER,
    }

    if target_level in owner_levels and actual_level in owner_levels:
        return None

    if target_level == PermissionLevel.DEFAULT:
        return f"/in-game command:nlrm {perm.namelayer} {perm.ign}"

    if actual_level == PermissionLevel.DEFAULT:
        return f"/in-game command:nlip {perm.namelayer} {perm.ign} {target_level.name}"

    return f"/in-game command:nlpp {perm.namelayer} {perm.ign} {target_level.name}"


async def _compare_and_update(old, new, repo):
    create = old is None and new.level != PermissionLevel.DEFAULT
    update = old is not None and new.level != PermissionLevel.DEFAULT
    delete = old is not None and new.level == PermissionLevel.DEFAULT

    if create:
        await repo.create(new)
        return ChangeKind.CREATED
    elif update:
        new.id = old.id
        await repo.update(new)
        return ChangeKind.UPDATED
    elif delete:
        await repo.delete(old.id)
        return ChangeKind.DELETED

    return None

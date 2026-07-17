import discord.ext.commands as commands
from helpers.discord import get_guild_roles, get_member
from models.permission import Permission, PermissionLevel
from models.permission_group import GroupPermission
from repositories.group_permissions import GroupPermissionsRepository
from repositories.people import PeopleRepository
from repositories.permission_exceptions import PermissionExceptionsRepository
from repositories.permissions import PermissionsRepository


class PermissionService:
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def update_actual_user_permission(self, permission: Permission):
        p_repo = PermissionsRepository()
        old = await p_repo.find_by_ign_and_namelayer(permission.ign, permission.namelayer)
        await _compare_and_update(old, permission, p_repo)

    async def update_user_permission(self, permission: Permission):
        pe_repo = PermissionExceptionsRepository()
        old = await pe_repo.find_by_ign_and_namelayer(permission.ign, permission.namelayer)
        await _compare_and_update(old, permission, pe_repo)

    async def update_group_permission(self, permission: GroupPermission):
        gp_repo = GroupPermissionsRepository()
        old = await gp_repo.find_by_role_id_and_namelayer(permission.role_id, permission.namelayer)
        await _compare_and_update(old, permission, gp_repo)

    async def get_user_permissions(self, user_ign: str) -> list[Permission]:
        people_repo = PeopleRepository()
        gp_repo = GroupPermissionsRepository()
        pe_repo = PermissionExceptionsRepository()

        person = await people_repo.find_by_ign(user_ign)
        member = await get_member(self.bot, person.user_id) if person is not None else None
        roles = member.roles if member is not None else []

        role_by_id = {role.id: role for role in roles}
        perm_map: dict[str, Permission] = {}

        def add_permission(permission: Permission) -> None:
            current = perm_map.get(permission.namelayer)

            if current is None or permission.level.value > current.level.value:
                perm_map[permission.namelayer] = permission

        for gp in await gp_repo.fetch_all():
            role = role_by_id.get(gp.role_id)
            if role is None:
                continue

            add_permission(
                Permission(
                    ign=user_ign,
                    namelayer=gp.namelayer,
                    level=gp.level,
                    source=role.mention,
                )
            )

        for exception in await pe_repo.fetch_by_ign(user_ign):
            add_permission(
                Permission(
                    ign=user_ign,
                    namelayer=exception.namelayer,
                    level=exception.level,
                    source="direct",
                )
            )

        return list(perm_map.values())

    async def get_namelayer_members(self, namelayer: str) -> list[Permission]:
        people_repo = PeopleRepository()
        gp_repo = GroupPermissionsRepository()
        pe_repo = PermissionExceptionsRepository()

        group_permissions = [
            gp
            for gp in await gp_repo.fetch_all()
            if gp.namelayer == namelayer
        ]

        people = await people_repo.fetch_all()
        ign_by_user_id = {
            person.user_id: person.in_game_name
            for person in people
        }

        roles = await get_guild_roles(self.bot, list(ign_by_user_id.keys()))
        role_by_id = {role.id: role for role in roles}

        perm_map: dict[str, Permission] = {}

        def add_permission(permission: Permission) -> None:
            current = perm_map.get(permission.ign)

            if current is None or permission.level.value > current.level.value:
                perm_map[permission.ign] = permission

        for gp in group_permissions:
            role = role_by_id.get(gp.role_id)
            if role is None:
                continue

            for member in role.members:
                ign = ign_by_user_id.get(member.id)
                if ign is None:
                    continue

                add_permission(
                    Permission(
                        ign=ign,
                        namelayer=namelayer,
                        level=gp.level,
                        source=role.mention,
                    )
                )

        for exception in await pe_repo.fetch_by_namelayer(namelayer):
            add_permission(
                Permission(
                    ign=exception.ign,
                    namelayer=namelayer,
                    level=exception.level,
                    source="direct",
                )
            )

        return list(perm_map.values())

    async def get_user_permission_commands(self, user_ign: str) -> list[str]:
        target_perms: list[Permission] = await self.get_user_permissions(user_ign)
        actual_perms: list[Permission] = await PermissionsRepository().fetch_by_ign(user_ign)

        target_by_nl = {p.namelayer: p for p in target_perms}
        actual_by_nl = {p.namelayer: p for p in actual_perms}

        return await _to_commands(target_by_nl, actual_by_nl)

    async def get_namelayer_member_commands(self, namelayer: str) -> list[str]:
        target_perms: list[Permission] = await self.get_namelayer_members(namelayer)
        actual_perms: list[Permission] = await PermissionsRepository().fetch_by_namelayer(namelayer)

        target_by_ign = {p.ign: p for p in target_perms}
        actual_by_ign = {p.ign: p for p in actual_perms}

        return await _to_commands(target_by_ign, actual_by_ign)

    async def import_permissions(self, entries):
        namelayers: list[str] = list(set(e.namelayer for e in entries))
        p_repo = PermissionsRepository()
        await p_repo.delete_by_namelayers(namelayers)
        await p_repo.batch_create(entries)

async def _to_commands(targets: dict[str, Permission], actuals: dict[str, Permission]):
    commands: list[str] = []
    all_keys = targets.keys() | actuals.keys()

    for key in sorted(all_keys):
        target = targets.get(key)
        actual = actuals.get(key)

        target_level = target.level if target else PermissionLevel.DEFAULT
        actual_level = actual.level if actual else PermissionLevel.DEFAULT

        cmd = await _to_command(target or actual, actual_level, target_level)
        if cmd: commands.append(cmd)

    return commands

async def _to_command(
    perm: Permission, actual_level: PermissionLevel, target_level: PermissionLevel
) -> str | None:
    if target_level == actual_level:
        return None

    owner_levels = {
        PermissionLevel.PRIMARY_OWNER,
        PermissionLevel.OWNER,
    }

    if target_level in owner_levels and actual_level in owner_levels:
        return None

    # Should not be in namelayer, but currently is
    if target_level == PermissionLevel.DEFAULT:
        return f"/in-game command:nlrm {perm.namelayer} {perm.ign}"

    # Should be in namelayer, but currently is not
    if actual_level == PermissionLevel.DEFAULT:
        return f"/in-game command:nlip {perm.namelayer} {perm.ign} {target_level.name}"

    # Already in namelayer, but wrong level
    return f"/in-game command:nlpp {perm.namelayer} {perm.ign} {target_level.name}"


async def _compare_and_update(old, new, repo):
    create = old is None and new.level != PermissionLevel.DEFAULT
    update = old is not None and new.level != PermissionLevel.DEFAULT
    delete = old is not None and new.level == PermissionLevel.DEFAULT

    if create:
        await repo.create(new)
    elif update:
        new.id = old.id
        await repo.update(new)
    elif delete:
        await repo.delete(old.id)
import discord.ext.commands as commands
from helpers.discord import get_guild_roles, get_member
from models.permission import Permission, PermissionLevel
from models.permission_group import GroupPermission
from repositories.group_permissions import GroupPermissionsRepository
from repositories.people import PeopleRepository
from repositories.permissions import PermissionsRepository


class PermissionService:
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def update_user_permission(self, permission: Permission):
        p_repo = PermissionsRepository()

        old = await p_repo.find_by_ign_and_namelayer(permission.ign, permission.namelayer)

        create = old is None and permission.level != PermissionLevel.DEFAULT
        update = old is not None and permission.level != PermissionLevel.DEFAULT
        delete = old is not None and permission.level == PermissionLevel.DEFAULT

        if create:
            await p_repo.create(permission)
        elif update:
            permission.id = old.id
            await p_repo.update(permission)
        elif delete:
            await p_repo.delete(old.id)

    async def update_group_permission(self, permission: GroupPermission):
        gp_repo = GroupPermissionsRepository()

        old = await gp_repo.find_by_role_id_and_namelayer(permission.role_id, permission.namelayer)

        create = old is None and permission.level != PermissionLevel.DEFAULT
        update = old is not None and permission.level != PermissionLevel.DEFAULT
        delete = old is not None and permission.level == PermissionLevel.DEFAULT

        if create:
            await gp_repo.create(permission)
        elif update:
            permission.id = old.id
            await gp_repo.update(permission)
        elif delete:
            await gp_repo.delete(old.id)

    async def _get_user_permissions(self, user_ign: str) -> list[Permission]:
        people_repo = PeopleRepository()
        gp_repo = GroupPermissionsRepository()

        # Find fitting user id
        person = await people_repo.find_by_ign(user_ign)
        if person is None:
            return []
        member = await get_member(self.bot, person.user_id)
        if member is None:
            return []

        # Get group permissions
        role_ids = [role.id for role in member.roles]
        group_permissions: list[GroupPermission] = [
            gp for gp in await gp_repo.fetch_all() if gp.role_id in role_ids
        ]

        perm_map: dict[str, int] = dict()
        for gp in group_permissions:
            key = gp.namelayer
            perm_map[key] = max(perm_map.get(key, 0), gp.level.value)

        return [
            Permission(ign=user_ign, namelayer=nl, level=PermissionLevel(level))
            for nl, level in perm_map.items()
        ]

    async def get_user_permission_commands(self, user_ign: str) -> list[str]:
        target_perms: list[Permission] = await self._get_user_permissions(user_ign)
        actual_perms: list[Permission] = await PermissionsRepository().fetch_by_ign(user_ign)

        commands: list[str] = []

        target_by_nl = {p.namelayer: p for p in target_perms}
        actual_by_nl = {p.namelayer: p for p in actual_perms}

        all_namelayers = target_by_nl.keys() | actual_by_nl.keys()

        for namelayer in sorted(all_namelayers):
            target = target_by_nl.get(namelayer)
            actual = actual_by_nl.get(namelayer)

            target_level = target.level if target else PermissionLevel.DEFAULT
            actual_level = actual.level if actual else PermissionLevel.DEFAULT

            if target_level == actual_level:
                continue

            commands.append(_to_command(target or actual, actual_level, target_level))

        return commands

    async def _get_namelayer_members(self, namelayer: str) -> list[Permission]:
        people_repo = PeopleRepository()
        gp_repo = GroupPermissionsRepository()

        group_permissions: list[GroupPermission] = [
            gp for gp in await gp_repo.fetch_all() if gp.namelayer == namelayer
        ]

        if not group_permissions:
            return []

        people = await people_repo.fetch_all()
        ign_by_user_id: dict[int, str] = {person.user_id: person.in_game_name for person in people}

        roles = await get_guild_roles(self.bot, list(ign_by_user_id.keys()))
        role_by_id = {role.id: role for role in roles}

        perm_map: dict[str, int] = {}

        for gp in group_permissions:
            role = role_by_id.get(gp.role_id)
            if role is None:
                continue

            for member in role.members:
                ign = ign_by_user_id.get(member.id)
                if ign is None:
                    continue

                perm_map[ign] = max(
                    perm_map.get(ign, PermissionLevel.DEFAULT.value),
                    gp.level.value,
                )

        return [
            Permission(
                ign=ign,
                namelayer=namelayer,
                level=PermissionLevel(level),
            )
            for ign, level in perm_map.items()
        ]

    async def get_namelayer_member_commands(self, namelayer: str) -> list[str]:
        target_perms: list[Permission] = await self._get_namelayer_members(namelayer)
        actual_perms: list[Permission] = await PermissionsRepository().fetch_by_namelayer(namelayer)

        commands: list[str] = []

        target_by_ign = {p.ign: p for p in target_perms}
        actual_by_ign = {p.ign: p for p in actual_perms}

        all_igns = target_by_ign.keys() | actual_by_ign.keys()

        for ign in sorted(all_igns):
            target = target_by_ign.get(ign)
            actual = actual_by_ign.get(ign)

            target_level = target.level if target else PermissionLevel.DEFAULT
            actual_level = actual.level if actual else PermissionLevel.DEFAULT

            if target_level == actual_level:
                continue

            commands.append(_to_command(target or actual, actual_level, target_level))

        return commands

    async def import_permissions(self, entries):
        namelayers: list[str] = list(set(e.namelayer for e in entries))
        p_repo = PermissionsRepository()
        await p_repo.delete_by_namelayers(namelayers)
        await p_repo.batch_create(entries)


def _to_command(
    perm: Permission, actual_level: PermissionLevel, target_level: PermissionLevel
) -> str:
    # Should not be in namelayer, but currently is
    if target_level == PermissionLevel.DEFAULT:
        return f"/in-game command:nlrm {perm.namelayer} {perm.ign}"

    # Should be in namelayer, but currently is not
    if actual_level == PermissionLevel.DEFAULT:
        return f"/in-game command:nlip {perm.namelayer} {perm.ign} {target_level.name}"

    # Already in namelayer, but wrong level
    return f"/in-game command:nlpp {perm.namelayer} {perm.ign} {target_level.name}"

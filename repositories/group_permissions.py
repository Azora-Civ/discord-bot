from helpers.general import connect
from models.permission import PermissionLevel
from models.permission_group import GroupPermission


class GroupPermissionsRepository:
    async def create_table(self) -> None:
        async with connect() as db:
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS group_permissions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    role_id INTEGER NOT NULL,
                    namelayer TEXT NOT NULL COLLATE NOCASE,
                    level TEXT NOT NULL,
    
                    UNIQUE(role_id, namelayer)
                )
                """
            )
            await db.commit()

    async def create(self, permission: GroupPermission) -> int:
        async with connect() as db:
            cursor = await db.execute(
                """
                INSERT INTO group_permissions (role_id, namelayer, level)
                VALUES (?, ?, ?)
                """,
                (
                    permission.role_id,
                    permission.namelayer,
                    permission.level.name,
                ),
            )
            await db.commit()
            return cursor.lastrowid

    async def update(self, permission: GroupPermission) -> None:
        if permission.id is None:
            raise ValueError("Cannot update group permission without id")

        async with connect() as db:
            await db.execute(
                """
                UPDATE group_permissions
                SET role_id = ?, namelayer = ?, level = ?
                WHERE id = ?
                """,
                (
                    permission.role_id,
                    permission.namelayer,
                    permission.level.name,
                    permission.id,
                ),
            )
            await db.commit()

    async def delete(self, permission_id: int) -> None:
        async with connect() as db:
            await db.execute(
                "DELETE FROM group_permissions WHERE id = ?",
                (permission_id,),
            )
            await db.commit()

    async def fetch_all(self) -> list[GroupPermission]:
        async with connect() as db:
            cursor = await db.execute("SELECT * FROM group_permissions")
            rows = await cursor.fetchall()
            return [self._from_row(row) for row in rows]

    async def find_by_role_id_and_namelayer(
        self,
        role_id: int,
        namelayer: str,
    ) -> GroupPermission | None:
        async with connect() as db:
            cursor = await db.execute(
                """
                SELECT * FROM group_permissions
                WHERE role_id = ? AND namelayer = ?
                """,
                (role_id, namelayer),
            )
            row = await cursor.fetchone()
            return self._from_row(row) if row else None

    async def correct_namelayer(self, namelayer: str) -> str | None:
        async with connect() as db:
            cursor = await db.execute(
                """
                SELECT * FROM group_permissions
                WHERE namelayer = ?
                LIMIT 1
                """,
                (namelayer,),
            )
            row = await cursor.fetchone()
            return self._from_row(row).namelayer if row else None

    def _from_row(self, row) -> GroupPermission:
        return GroupPermission(
            id=row["id"],
            role_id=row["role_id"],
            namelayer=row["namelayer"],
            level=PermissionLevel[row["level"]],
        )

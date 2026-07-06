from typing import List

from models.permission import Permission, PermissionLevel
from repositories.database import connect


class PermissionsRepository:
    async def create_table(self) -> None:
        async with connect() as db:
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS permissions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ign TEXT NOT NULL,
                    namelayer TEXT NOT NULL,
                    level TEXT NOT NULL,
    
                    UNIQUE(ign, namelayer)
                )
                """
            )
            await db.commit()

    async def create(self, permission: Permission) -> int:
        async with connect() as db:
            cursor = await db.execute(
                """
                INSERT INTO permissions (ign, namelayer, level)
                VALUES (?, ?, ?)
                """,
                (
                    permission.ign,
                    permission.namelayer,
                    permission.level.name,
                ),
            )
            await db.commit()
            return cursor.lastrowid

    async def update(self, permission: Permission) -> None:
        if permission.id is None:
            raise ValueError("Cannot update permission without id")

        async with connect() as db:
            await db.execute(
                """
                UPDATE permissions
                SET ign = ?, namelayer = ?, level = ?
                WHERE id = ?
                """,
                (
                    permission.ign,
                    permission.namelayer,
                    permission.level.name,
                    permission.id,
                ),
            )
            await db.commit()

    async def delete(self, permission_id: int) -> None:
        async with connect() as db:
            await db.execute(
                "DELETE FROM permissions WHERE id = ?",
                (permission_id,),
            )
            await db.commit()

    async def fetch_all(self) -> List[Permission]:
        async with connect() as db:
            cursor = await db.execute("SELECT * FROM permissions")
            rows = await cursor.fetchall()
            return [self._from_row(row) for row in rows]

    async def fetch_by_ign(self, ign: str) -> List[Permission]:
        async with connect() as db:
            cursor = await db.execute(
                "SELECT * FROM permissions WHERE ign = ?",
                (ign,),
            )
            rows = await cursor.fetchall()
            return [self._from_row(row) for row in rows]

    async def fetch_by_namelayer(self, namelayer: str) -> List[Permission]:
        async with connect() as db:
            cursor = await db.execute(
                "SELECT * FROM permissions WHERE namelayer = ?",
                (namelayer,),
            )
            rows = await cursor.fetchall()
            return [self._from_row(row) for row in rows]

    async def find_by_ign_and_namelayer(
        self,
        ign: str,
        namelayer: str,
    ) -> Permission | None:
        async with connect() as db:
            cursor = await db.execute(
                """
                SELECT * FROM permissions
                WHERE ign = ? AND namelayer = ?
                """,
                (ign, namelayer),
            )
            row = await cursor.fetchone()
            return self._from_row(row) if row else None

    def _from_row(self, row) -> Permission:
        return Permission(
            id=row["id"],
            ign=row["ign"],
            namelayer=row["namelayer"],
            level=PermissionLevel[row["level"]],
        )

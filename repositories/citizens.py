from datetime import datetime
from typing import TYPE_CHECKING

from models.citizen import Citizen, Citizenship

if TYPE_CHECKING:
    from database import Database


class CitizenRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    async def create_table(self) -> None:
        async with self.db.transaction() as conn:
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS citizens (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    in_game_name TEXT NOT NULL COLLATE NOCASE UNIQUE,
                    user_id INTEGER UNIQUE,
                    citizenship TEXT NOT NULL,
                    joined_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    last_online TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

    async def create(self, citizen: Citizen) -> int:
        async with self.db.transaction() as conn:
            cursor = await conn.execute(
                """
                INSERT INTO citizens (
                    in_game_name,
                    user_id,
                    citizenship,
                    joined_at,
                    last_online
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    citizen.in_game_name,
                    citizen.user_id,
                    citizen.citizenship.name,
                    citizen.joined_at.isoformat(),
                    citizen.last_online.isoformat(),
                ),
            )
            return int(cursor.lastrowid)

    async def update(self, citizen: Citizen) -> None:
        if citizen.id is None:
            raise ValueError("Cannot update citizen without id")

        async with self.db.transaction() as conn:
            await conn.execute(
                """
                UPDATE citizens
                SET
                    in_game_name = ?,
                    user_id = ?,
                    citizenship = ?,
                    joined_at = ?,
                    last_online = ?
                WHERE id = ?
                """,
                (
                    citizen.in_game_name,
                    citizen.user_id,
                    citizen.citizenship.name,
                    citizen.joined_at.isoformat(),
                    citizen.last_online.isoformat(),
                    citizen.id,
                ),
            )

    async def delete(self, citizen_id: int) -> None:
        async with self.db.transaction() as conn:
            await conn.execute(
                "DELETE FROM citizens WHERE id = ?",
                (citizen_id,),
            )

    async def fetch_by_id(self, citizen_id: int) -> Citizen | None:
        async with self.db.transaction() as conn:
            cursor = await conn.execute(
                """
                SELECT *
                FROM citizens
                WHERE id = ?
                """,
                (citizen_id,),
            )
            row = await cursor.fetchone()
            return self._from_row(row) if row else None

    async def fetch_by_user_id(self, user_id: int) -> Citizen | None:
        async with self.db.transaction() as conn:
            cursor = await conn.execute(
                """
                SELECT *
                FROM citizens
                WHERE user_id = ?
                """,
                (user_id,),
            )
            row = await cursor.fetchone()
            return self._from_row(row) if row else None

    async def fetch_by_ign(self, ign: str) -> Citizen | None:
        async with self.db.transaction() as conn:
            cursor = await conn.execute(
                """
                SELECT *
                FROM citizens
                WHERE in_game_name = ?
                """,
                (ign,),
            )
            row = await cursor.fetchone()
            return self._from_row(row) if row else None

    async def fetch_all(self) -> list[Citizen]:
        async with self.db.transaction() as conn:
            cursor = await conn.execute(
                """
                SELECT *
                FROM citizens
                ORDER BY in_game_name
                """
            )
            rows = await cursor.fetchall()
            return [self._from_row(row) for row in rows]

    def _from_row(self, row) -> Citizen:
        return Citizen(
            id=row["id"],
            in_game_name=row["in_game_name"],
            user_id=row["user_id"],
            citizenship=self._citizenship_from_db(row["citizenship"]),
            joined_at=datetime.fromisoformat(row["joined_at"]),
            last_online=datetime.fromisoformat(row["last_online"]),
        )

    def _citizenship_from_db(self, value: str) -> Citizenship:
        try:
            return Citizenship[value]
        except KeyError:
            return Citizenship(value)

import json
from dataclasses import asdict, fields
from datetime import datetime
from typing import TYPE_CHECKING

from models.citizen import Citizen, CitizenData, Citizenship

if TYPE_CHECKING:
    from database import Database


class CitizenRepository:
    def __init__(self, db: "Database") -> None:
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
                    data TEXT NOT NULL DEFAULT '{}',
                    joined_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    last_online TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            await self._ensure_data_column(conn)

    async def _ensure_data_column(self, conn) -> None:
        cursor = await conn.execute("PRAGMA table_info(citizens)")
        columns = {row["name"] for row in await cursor.fetchall()}
        if "data" not in columns:
            await conn.execute("ALTER TABLE citizens ADD COLUMN data TEXT NOT NULL DEFAULT '{}'")

    async def create(self, citizen: Citizen) -> int:
        async with self.db.transaction() as conn:
            cursor = await conn.execute(
                """
                INSERT INTO citizens (
                    in_game_name,
                    user_id,
                    citizenship,
                    data,
                    joined_at,
                    last_online
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    citizen.in_game_name,
                    citizen.user_id,
                    citizen.citizenship.name,
                    self._data_to_json(citizen.data),
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
                    data = ?,
                    joined_at = ?,
                    last_online = ?
                WHERE id = ?
                """,
                (
                    citizen.in_game_name,
                    citizen.user_id,
                    citizen.citizenship.name,
                    self._data_to_json(citizen.data),
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
            data=self._data_from_json(row["data"]),
            joined_at=datetime.fromisoformat(row["joined_at"]),
            last_online=datetime.fromisoformat(row["last_online"]),
        )

    def _data_to_json(self, data: CitizenData) -> str:
        return json.dumps(asdict(data))

    def _data_from_json(self, value: str) -> CitizenData:
        raw_data = json.loads(value) if value else {}
        field_names = {field.name for field in fields(CitizenData)}
        data = {key: raw_data[key] for key in field_names if key in raw_data}
        return CitizenData(**data)

    def _citizenship_from_db(self, value: str) -> Citizenship:
        if value in {"CITIZEN", "Citizen"}:
            return Citizenship.PRIMARY_CITIZEN

        try:
            return Citizenship[value]
        except KeyError:
            return Citizenship(value)

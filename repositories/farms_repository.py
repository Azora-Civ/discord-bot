import json
from typing import TYPE_CHECKING, Any

from models.farm import Farm

if TYPE_CHECKING:
    from database import Database


class FarmsRepository:
    def __init__(self, db: "Database") -> None:
        self.db = db

    async def create_table(self) -> None:
        async with self.db.transaction() as conn:
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS farms (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL COLLATE NOCASE UNIQUE,
                    posxyz TEXT NOT NULL,
                    regrow_time INTEGER NOT NULL,
                    farm_time INTEGER NOT NULL,
                    started_time INTEGER,
                    finished_time INTEGER,
                    additional_data TEXT NOT NULL DEFAULT '{}'
                )
                """
            )

    async def set(self, farm: Farm) -> int:
        async with self.db.transaction() as conn:
            cursor = await conn.execute(
                """
                INSERT INTO farms (
                    name,
                    posxyz,
                    regrow_time,
                    farm_time,
                    started_time,
                    finished_time,
                    additional_data
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(name) DO UPDATE SET
                    name = excluded.name,
                    posxyz = excluded.posxyz,
                    regrow_time = excluded.regrow_time,
                    farm_time = excluded.farm_time
                RETURNING id
                """,
                (
                    farm.name,
                    farm.posxyz,
                    farm.regrow_time,
                    farm.farm_time,
                    farm.started_time,
                    farm.finished_time,
                    json.dumps(farm.additional_data),
                ),
            )
            row = await cursor.fetchone()
            return row["id"]

    async def delete_by_name(self, name: str) -> bool:
        async with self.db.transaction() as conn:
            cursor = await conn.execute(
                """
                DELETE FROM farms
                WHERE name = ?
                """,
                (name,),
            )
            return cursor.rowcount > 0

    async def find_by_name(self, name: str) -> Farm | None:
        async with self.db.transaction() as conn:
            cursor = await conn.execute(
                """
                SELECT *
                FROM farms
                WHERE name = ?
                """,
                (name,),
            )
            row = await cursor.fetchone()

        if row is None:
            return None

        return _farm_from_row(row)

    async def fetch_all(self) -> list[Farm]:
        async with self.db.transaction() as conn:
            cursor = await conn.execute(
                """
                SELECT *
                FROM farms
                ORDER BY name
                """
            )
            rows = await cursor.fetchall()

        return [_farm_from_row(row) for row in rows]

    async def update_started_time(
        self,
        name: str,
        started_time: int,
        *,
        last_farmed_by: str | None = None,
    ) -> bool:
        return await self._update_time(name, "started_time", started_time, last_farmed_by=last_farmed_by)

    async def update_finished_time(
        self,
        name: str,
        finished_time: int,
        *,
        last_farmed_by: str | None = None,
    ) -> bool:
        return await self._update_time(name, "finished_time", finished_time, last_farmed_by=last_farmed_by)

    async def _update_time(
        self,
        name: str,
        column: str,
        value: int,
        *,
        last_farmed_by: str | None = None,
    ) -> bool:
        if column not in {"started_time", "finished_time"}:
            raise ValueError(f"Invalid farm time column: {column}")

        async with self.db.transaction() as conn:
            select_cursor = await conn.execute(
                """
                SELECT additional_data
                FROM farms
                WHERE name = ?
                """,
                (name,),
            )
            row = await select_cursor.fetchone()
            if row is None:
                return False

            try:
                additional_data = json.loads(row["additional_data"])
            except json.JSONDecodeError:
                additional_data = {}

            if last_farmed_by is not None:
                additional_data["last_farmed_by"] = last_farmed_by

            cursor = await conn.execute(
                f"""
                UPDATE farms
                SET {column} = ?,
                    additional_data = ?
                WHERE name = ?
                """,
                (value, json.dumps(additional_data), name),
            )
            return cursor.rowcount > 0


def _farm_from_row(row: Any) -> Farm:
    return Farm(
        id=row["id"],
        name=row["name"],
        posxyz=row["posxyz"],
        regrow_time=row["regrow_time"],
        farm_time=row["farm_time"],
        started_time=row["started_time"],
        finished_time=row["finished_time"],
        additional_data=json.loads(row["additional_data"]),
    )

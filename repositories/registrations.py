import json
from dataclasses import asdict, fields

from helpers.general import connect
from models.citizen import Citizenship
from models.registration import Registration, RegistrationData, RegistrationStatus


class RegistrationRepository:
    async def create_table(self) -> None:
        async with connect() as db:
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS registrations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    poster_id INTEGER NOT NULL,
                    is_for_self INTEGER NOT NULL,
                    citizenship_type TEXT NOT NULL,
                    in_game_name TEXT NOT NULL COLLATE NOCASE,
                    data TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'PENDING'
                )
                """
            )
            await db.commit()

    async def create(self, registration: Registration) -> int:
        async with connect() as db:
            cursor = await db.execute(
                """
                INSERT INTO registrations (
                    poster_id,
                    is_for_self,
                    citizenship_type,
                    in_game_name,
                    data,
                    status
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    registration.poster_id,
                    int(registration.is_for_self),
                    registration.citizenship_type.name,
                    registration.in_game_name,
                    self._data_to_json(registration.data),
                    registration.status.name,
                ),
            )
            await db.commit()
            return int(cursor.lastrowid)

    async def update(self, registration: Registration) -> None:
        if registration.id is None:
            raise ValueError("Cannot update registration without id")

        async with connect() as db:
            await db.execute(
                """
                UPDATE registrations
                SET
                    poster_id = ?,
                    is_for_self = ?,
                    citizenship_type = ?,
                    in_game_name = ?,
                    data = ?,
                    status = ?
                WHERE id = ?
                """,
                (
                    registration.poster_id,
                    int(registration.is_for_self),
                    registration.citizenship_type.name,
                    registration.in_game_name,
                    self._data_to_json(registration.data),
                    registration.status.name,
                    registration.id,
                ),
            )
            await db.commit()

    async def delete(self, registration_id: int) -> None:
        async with connect() as db:
            await db.execute(
                "DELETE FROM registrations WHERE id = ?",
                (registration_id,),
            )
            await db.commit()

    async def fetch_by_id(self, registration_id: int) -> Registration | None:
        async with connect() as db:
            cursor = await db.execute(
                """
                SELECT *
                FROM registrations
                WHERE id = ?
                """,
                (registration_id,),
            )
            row = await cursor.fetchone()
            return self._from_row(row) if row else None

    async def fetch_by_user_id(self, poster_id: int) -> Registration | None:
        async with connect() as db:
            cursor = await db.execute(
                """
                SELECT *
                FROM registrations
                WHERE poster_id = ?
                """,
                (poster_id,),
            )
            row = await cursor.fetchone()
            return self._from_row(row) if row else None

    async def fetch_by_ign(self, ign: str) -> Registration | None:
        async with connect() as db:
            cursor = await db.execute(
                """
                SELECT *
                FROM registrations
                WHERE in_game_name = ?
                """,
                (ign,),
            )
            row = await cursor.fetchone()
            return self._from_row(row) if row else None

    async def fetch_all(self) -> list[Registration]:
        async with connect() as db:
            cursor = await db.execute(
                """
                SELECT *
                FROM registrations
                ORDER BY id
                """
            )
            rows = await cursor.fetchall()
            return [self._from_row(row) for row in rows]

    async def fetch_by_thread_id(self, thread_id: int) -> Registration | None:
        async with connect() as db:
            cursor = await db.execute(
                """
                SELECT *
                FROM registrations
                WHERE json_extract(data, '$.thread_id') = ?
                """,
                (thread_id,),
            )
            row = await cursor.fetchone()
            return self._from_row(row) if row else None

    def _from_row(self, row) -> Registration:
        return Registration(
            id=row["id"],
            poster_id=row["poster_id"],
            is_for_self=bool(row["is_for_self"]),
            citizenship_type=self._citizenship_from_db(row["citizenship_type"]),
            in_game_name=row["in_game_name"],
            data=self._data_from_json(row["data"]),
            status=self._status_from_db(row["status"]),
        )

    def _data_to_json(self, data: RegistrationData) -> str:
        return json.dumps(asdict(data))

    def _data_from_json(self, value: str) -> RegistrationData:
        raw_data = json.loads(value) if value else {}
        field_names = {field.name for field in fields(RegistrationData)}
        data = {key: raw_data[key] for key in field_names if key in raw_data}
        return RegistrationData(**data)

    def _citizenship_from_db(self, value: str) -> Citizenship:
        try:
            return Citizenship[value]
        except KeyError:
            return Citizenship(value)

    def _status_from_db(self, value: str) -> RegistrationStatus:
        try:
            return RegistrationStatus[value]
        except KeyError:
            return RegistrationStatus(value)

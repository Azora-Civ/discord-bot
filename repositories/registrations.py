from typing import List

import aiosqlite
from database import connect
from models.registration import Registration

class RegistrationRepository:
    async def create_table(self) -> None:
        async with connect() as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS registrations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    citizenship_type TEXT NOT NULL,
                    in_game_name TEXT NOT NULL,
                    about TEXT NOT NULL,
                    follow_rules TEXT NOT NULL,
                    citizenry TEXT NOT NULL,
                    snitch_hit INTEGER NOT NULL DEFAULT 0,

                    thread_id INTEGER NOT NULL,
                    message_id INTEGER NOT NULL,

                    status TEXT NOT NULL DEFAULT 'pending',
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            await db.commit()

    async def create(self, registration: Registration) -> Registration:
        async with connect() as db:
            cursor = await db.execute("""
                INSERT INTO registrations (
                    user_id,
                    citizenship_type,
                    in_game_name,
                    about,
                    follow_rules,
                    citizenry,
                    snitch_hit,
                    thread_id,
                    message_id,
                    status
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                registration.user_id,
                registration.citizenship_type,
                registration.in_game_name,
                registration.about,
                registration.follow_rules,
                registration.citizenry,
                int(registration.snitch_hit),
                registration.thread_id,
                registration.message_id,
                registration.status,
            ))
            await db.commit()
            registration_id = cursor.lastrowid

        created = await self.get_by_id(registration_id)
        if created is None:
            raise RuntimeError("Failed to fetch created registration")

        return created

    async def update(self, registration: Registration) -> None:
        if registration.id is None:
            raise ValueError("Cannot update registration without id")

        async with connect() as db:
            await db.execute("""
                UPDATE registrations
                SET
                    user_id = ?,
                    citizenship_type = ?,
                    in_game_name = ?,
                    about = ?,
                    follow_rules = ?,
                    citizenry = ?,
                    snitch_hit = ?,
                    thread_id = ?,
                    message_id = ?,
                    status = ?
                WHERE id = ?
            """, (
                registration.user_id,
                registration.citizenship_type,
                registration.in_game_name,
                registration.about,
                registration.follow_rules,
                registration.citizenry,
                int(registration.snitch_hit),
                registration.thread_id,
                registration.message_id,
                registration.status,
                registration.id,
            ))
            await db.commit()

    async def upsert(self, registration: Registration) -> None:
        if registration.id is None:
            new = await self.create(registration)
            registration.id = new.id
        else:
            await self.update(registration)

    async def get_by_id(self, registration_id: int) -> Registration | None:
        async with connect() as db:
            cursor = await db.execute("""
                SELECT *
                FROM registrations
                WHERE id = ?
            """, (registration_id,))
            row = await cursor.fetchone()

        return self._row_to_registration(row) if row else None

    async def get_by_user_id(self, user_id: int) -> List[Registration]:
        async with connect() as db:
            cursor = await db.execute("""
                SELECT *
                FROM registrations
                WHERE user_id = ?
            """, (user_id,))
            rows = await cursor.fetchall()

        return [self._row_to_registration(row) for row in rows]

    async def get_by_ign(self, ign):
        async with connect() as db:
            cursor = await db.execute("""
                SELECT *
                FROM registrations
                WHERE in_game_name = ?
            """, (ign,))
            row = await cursor.fetchone()

        return self._row_to_registration(row) if row else None

    async def get_by_thread_id(self, thread_id: int) -> Registration | None:
        async with connect() as db:
            cursor = await db.execute("""
                SELECT *
                FROM registrations
                WHERE thread_id = ?
            """, (thread_id,))
            row = await cursor.fetchone()

        return self._row_to_registration(row) if row else None

    async def delete(self, registration_id: int) -> None:
        async with connect() as db:
            await db.execute("""
                DELETE FROM registrations
                WHERE id = ?
            """, (registration_id,))
            await db.commit()

    def _row_to_registration(self, row: aiosqlite.Row) -> Registration:
        return Registration(
            id=row["id"],
            user_id=row["user_id"],
            citizenship_type=row["citizenship_type"],
            in_game_name=row["in_game_name"],
            about=row["about"],
            follow_rules=row["follow_rules"],
            citizenry=row["citizenry"],
            snitch_hit=bool(row["snitch_hit"]),
            thread_id=row["thread_id"],
            message_id=row["message_id"],
            status=row["status"],
            created_at=row["created_at"],
        )

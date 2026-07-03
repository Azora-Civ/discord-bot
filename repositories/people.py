from helpers.general import connect
from models.person import Person


class PeopleRepository:
    async def create_table(self) -> None:
        async with connect() as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS people (
                    user_id INTEGER PRIMARY KEY,
                    in_game_name TEXT NOT NULL,
                    citizenship TEXT NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            await db.commit()

    async def get_by_user_id(self, user_id: int) -> Person | None:
        async with connect() as db:
            cursor = await db.execute(
                """
                SELECT user_id, in_game_name, citizenship, created_at
                FROM people
                WHERE user_id = ?
                """,
                (user_id,),
            )

            row = await cursor.fetchone()

            if row is None:
                return None

            return self._row_to_person(row)

    async def create(self, person: Person) -> None:
        async with connect() as db:
            await db.execute(
                """
                INSERT INTO people (user_id, in_game_name, citizenship)
                VALUES (?, ?, ?)
                """,
                (person.user_id, person.in_game_name, person.citizenship),
            )
            await db.commit()

    async def update(self, person: Person) -> None:
        async with connect() as db:
            await db.execute(
                """
                UPDATE people
                SET in_game_name = ?, citizenship = ?
                WHERE user_id = ?
                """,
                (person.in_game_name, person.citizenship, person.user_id),
            )
            await db.commit()

    async def upsert(self, person: Person) -> None:
        async with connect() as db:
            await db.execute(
                """
                INSERT INTO people (user_id, in_game_name, citizenship)
                VALUES (?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    in_game_name = excluded.in_game_name,
                    citizenship = excluded.citizenship
                """,
                (person.user_id, person.in_game_name, person.citizenship),
            )
            await db.commit()

    async def delete(self, user_id: int) -> None:
        async with connect() as db:
            await db.execute(
                """
                DELETE FROM people
                WHERE user_id = ?
                """,
                (user_id,),
            )
            await db.commit()

    async def list_all(self) -> list[Person]:
        async with connect() as db:
            cursor = await db.execute(
                """
                SELECT user_id, in_game_name, citizenship, created_at
                FROM people
                ORDER BY in_game_name
                """
            )

            rows = await cursor.fetchall()

            return [self._row_to_person(row) for row in rows]

    async def list_by_citizenship(self, citizenship: str) -> list[Person]:
        async with connect() as db:
            cursor = await db.execute(
                """
                SELECT user_id, in_game_name, citizenship, created_at
                FROM people
                WHERE citizenship = ?
                ORDER BY in_game_name
                """,
                (citizenship,),
            )

            rows = await cursor.fetchall()

            return [self._row_to_person(row) for row in rows]

    def _row_to_person(self, row) -> Person:
        return Person(
            user_id=row["user_id"],
            in_game_name=row["in_game_name"],
            citizenship=row["citizenship"],
            created_at=row["created_at"],
        )

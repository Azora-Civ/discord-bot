from database import connect


class KeyValueRepository:
    async def create_table(self) -> None:
        async with connect() as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS key_values (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                )
            """)
            await db.commit()

    async def get(self, key: str) -> str | None:
        async with connect() as db:
            cursor = await db.execute(
                """
                SELECT value
                FROM key_values
                WHERE key = ?
                """,
                (key,),
            )

            row = await cursor.fetchone()

            if row is None:
                return None

            return row["value"]

    async def set(self, key: str, value: str) -> None:
        async with connect() as db:
            await db.execute(
                """
                INSERT INTO key_values (key, value)
                VALUES (?, ?)
                ON CONFLICT(key) DO UPDATE SET
                    value = excluded.value
                """,
                (key, value),
            )
            await db.commit()

    async def delete(self, key: str) -> None:
        async with connect() as db:
            await db.execute(
                """
                DELETE FROM key_values
                WHERE key = ?
                """,
                (key,),
            )
            await db.commit()

    async def exists(self, key: str) -> bool:
        value = await self.get(key)
        return value is not None

    # ===== HELPERS =====

    async def get_int(self, key: str) -> int | None:
        value = await self.get(key)

        if value is None:
            return None

        return int(value)

    async def set_int(self, key: str, value: int) -> None:
        await self.set(key, str(value))

    async def get_bool(self, key: str) -> bool | None:
        value = await self.get(key)

        if value is None:
            return None

        return value.lower() in ("true", "1", "yes", "on")

    async def set_bool(self, key: str, value: bool) -> None:
        await self.set(key, "true" if value else "false")
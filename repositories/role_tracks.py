from typing import TYPE_CHECKING

from models.role_track import RoleTrack

if TYPE_CHECKING:
    from database import Database


class RoleTracksRepository:
    def __init__(self, db: "Database") -> None:
        self.db = db

    async def create_table(self) -> None:
        async with self.db.transaction() as conn:
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS role_tracks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL COLLATE NOCASE UNIQUE
                )
                """
            )
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS role_track_roles (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    track_id INTEGER NOT NULL,
                    role_id INTEGER NOT NULL,
                    position INTEGER NOT NULL,

                    UNIQUE(track_id, role_id),
                    UNIQUE(track_id, position),
                    FOREIGN KEY(track_id) REFERENCES role_tracks(id) ON DELETE CASCADE
                )
                """
            )

    async def set(self, track: RoleTrack) -> int:
        async with self.db.transaction() as conn:
            cursor = await conn.execute(
                """
                INSERT INTO role_tracks (name)
                VALUES (?)
                ON CONFLICT(name) DO UPDATE SET name = excluded.name
                RETURNING id
                """,
                (track.name,),
            )
            row = await cursor.fetchone()
            track_id = row["id"]

            await conn.execute("DELETE FROM role_track_roles WHERE track_id = ?", (track_id,))
            await conn.executemany(
                """
                INSERT INTO role_track_roles (track_id, role_id, position)
                VALUES (?, ?, ?)
                """,
                [(track_id, role_id, position) for position, role_id in enumerate(track.role_ids)],
            )

            return track_id

    async def fetch_all(self) -> list[RoleTrack]:
        async with self.db.transaction() as conn:
            cursor = await conn.execute(
                """
                SELECT rt.id, rt.name, rtr.role_id
                FROM role_tracks rt
                JOIN role_track_roles rtr ON rtr.track_id = rt.id
                ORDER BY rt.name, rtr.position
                """
            )
            rows = await cursor.fetchall()

        tracks_by_id: dict[int, RoleTrack] = {}
        for row in rows:
            track = tracks_by_id.setdefault(row["id"], RoleTrack(id=row["id"], name=row["name"], role_ids=[]))
            track.role_ids.append(row["role_id"])

        return list(tracks_by_id.values())

    async def find_by_name(self, name: str) -> RoleTrack | None:
        async with self.db.transaction() as conn:
            cursor = await conn.execute(
                """
                SELECT rt.id, rt.name, rtr.role_id
                FROM role_tracks rt
                JOIN role_track_roles rtr ON rtr.track_id = rt.id
                WHERE rt.name = ?
                ORDER BY rtr.position
                """,
                (name,),
            )
            rows = await cursor.fetchall()

        if not rows:
            return None

        return RoleTrack(
            id=rows[0]["id"],
            name=rows[0]["name"],
            role_ids=[row["role_id"] for row in rows],
        )

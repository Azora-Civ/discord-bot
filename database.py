import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path

import aiosqlite

from config import DB_BACKUP_DIR, DB_MAX_BACKUPS
from repositories.citizens import CitizenRepository
from repositories.group_permissions import GroupPermissionsRepository
from repositories.key_values import KeyValueRepository
from repositories.permission_exceptions import PermissionExceptionsRepository
from repositories.permissions import PermissionsRepository
from repositories.registrations import RegistrationRepository

log = logging.getLogger(__name__)


async def backup_db(path: str | Path):
    db_path = Path(path)

    if not db_path.exists():
        log.info("Skipping database backup; database does not exist yet: %s", db_path)
        return None

    DB_BACKUP_DIR.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(UTC).strftime("%Y-%m-%d_%H-%M-%S")
    backup_path = DB_BACKUP_DIR / f"bot_{timestamp}.db"

    log.info("Backing up database: %s -> %s", db_path, backup_path)

    try:
        async with aiosqlite.connect(db_path) as source:
            async with aiosqlite.connect(backup_path) as target:
                await source.backup(target)
    except Exception:
        log.exception("Database backup failed")
        raise

    log.info("Database backup completed: %s", backup_path)

    backups = sorted(
        DB_BACKUP_DIR.glob("bot_*.db"),
        key=lambda p: p.stat().st_mtime,
    )

    excess_count = len(backups) - DB_MAX_BACKUPS

    if excess_count > 0:
        log.info(
            "Removing %d old database backup(s); keeping newest %d",
            excess_count,
            DB_MAX_BACKUPS,
        )

    for old_backup in backups[:excess_count]:
        try:
            old_backup.unlink()
            log.info("Deleted old database backup: %s", old_backup)
        except Exception:
            log.exception("Failed to delete old database backup: %s", old_backup)

    return backup_path


class Database:
    def __init__(self, path: str):
        self.path = path
        self.connection: aiosqlite.Connection | None = None

        self._transaction_lock = asyncio.Lock()

        self.citizens = CitizenRepository(self)
        self.key_values = KeyValueRepository(self)
        self.registrations = RegistrationRepository(self)
        self.permissions = PermissionsRepository(self)
        self.permission_exceptions = PermissionExceptionsRepository(self)
        self.group_permissions = GroupPermissionsRepository(self)

    async def connect(self) -> None:
        await backup_db(self.path)

        self.connection = await aiosqlite.connect(self.path)
        self.connection.row_factory = aiosqlite.Row

        await self.connection.execute("PRAGMA foreign_keys = ON")
        await self.connection.execute("PRAGMA journal_mode = WAL")

        log.info("Initializing database")

        repos = [
            self.citizens,
            self.key_values,
            self.registrations,
            self.permissions,
            self.permission_exceptions,
            self.group_permissions,
        ]

        for repo in repos:
            await repo.create_table()

        log.info("Database initialized")

    async def close(self) -> None:
        if self.connection is not None:
            await self.connection.close()
            self.connection = None

    @asynccontextmanager
    async def transaction(self):
        conn = self.conn

        async with self._transaction_lock:
            await conn.execute("BEGIN")

            try:
                yield conn
            except Exception:
                await conn.rollback()
                raise
            else:
                await conn.commit()

    @property
    def conn(self) -> aiosqlite.Connection:
        if self.connection is None:
            raise RuntimeError("Database is not connected")
        return self.connection

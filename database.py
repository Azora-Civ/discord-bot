import asyncio
import logging
from contextlib import asynccontextmanager
import aiosqlite
from repositories.citizens import CitizenRepository
from repositories.group_permissions import GroupPermissionsRepository
from repositories.key_values import KeyValueRepository
from repositories.permission_exceptions import PermissionExceptionsRepository
from repositories.permissions import PermissionsRepository
from repositories.registrations import RegistrationRepository

log = logging.getLogger(__name__)


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

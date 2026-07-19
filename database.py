import logging
from datetime import UTC, datetime

import aiosqlite

from config import DB_BACKUP_DIR, DB_MAX_BACKUPS, DB_PATH
from repositories.citizens import CitizenRepository
from repositories.group_permissions import GroupPermissionsRepository
from repositories.key_values import KeyValueRepository
from repositories.permission_exceptions import PermissionExceptionsRepository
from repositories.permissions import PermissionsRepository
from repositories.registrations import RegistrationRepository

log = logging.getLogger(__name__)


async def backup_db():
    DB_BACKUP_DIR.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(UTC).strftime("%Y-%m-%d_%H-%M-%S")
    backup_path = DB_BACKUP_DIR / f"bot_{timestamp}.db"

    log.info("Backing up database: %s -> %s", DB_PATH, backup_path)

    try:
        async with aiosqlite.connect(DB_PATH) as source:
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


async def init_db():
    log.info("Initializing database")

    await backup_db()

    await CitizenRepository().create_table()
    await KeyValueRepository().create_table()
    await RegistrationRepository().create_table()
    await PermissionsRepository().create_table()
    await PermissionExceptionsRepository().create_table()
    await GroupPermissionsRepository().create_table()

    log.info("Database initialized")

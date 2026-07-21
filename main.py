import asyncio
import logging
import os
import signal
from collections.abc import Iterator
from contextlib import contextmanager

import discord
from discord.ext import commands

from config import DB_PATH, GUILD, TOKEN
from database import Database
from services.citizen_service import CitizenService
from services.permission_service import PermissionService
from services.registration_service import RegistrationService
from setup_logging import setup_logging

setup_logging()
log = logging.getLogger(__name__)

SHUTDOWN_TIMEOUT_SECONDS = 30


class RoyalSteward(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True

        self.db = Database(DB_PATH)
        self.citizen_service = CitizenService(self.db)
        self.registration_service = RegistrationService(self.db, self.citizen_service)
        self.permission_service = PermissionService(self.db)

        self.is_closing = False
        self._accepting_interactions = True
        self._active_interactions = 0
        self._interactions_idle = asyncio.Event()
        self._interactions_idle.set()

        # Keep track of background tasks
        self._background_tasks: set[asyncio.Task] = set()

        super().__init__(
            command_prefix="!",
            intents=intents,
        )

    def create_task(self, coro, *, name: str | None = None) -> asyncio.Task:
        """Create, track, and log failures from a background task."""
        task = asyncio.create_task(coro, name=name)
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)
        task.add_done_callback(self._log_background_task_result)
        return task

    def _log_background_task_result(self, task: asyncio.Task) -> None:
        if task.cancelled():
            return

        try:
            task.result()
        except Exception:
            log.exception("Background task failed: %s", task.get_name())

    @contextmanager
    def interaction_lease(self) -> Iterator[bool]:
        if not self._accepting_interactions:
            yield False
            return

        self._active_interactions += 1
        self._interactions_idle.clear()

        try:
            yield True
        finally:
            self._active_interactions -= 1
            if self._active_interactions == 0:
                self._interactions_idle.set()

    async def setup_hook(self) -> None:
        await self.db.connect()
        await self.load_extension("cogs.citizens_cog")
        await self.load_extension("cogs.registration_cog")
        await self.load_extension("cogs.permissions_cog")
        await self.load_extension("cogs.tracks_cog")

        synced = await self.tree.sync(guild=GUILD)
        log.info(f"Logged in as {self.user}")
        log.info(f"Synced {len(synced)} command(s)")

    async def close(self):
        if self.is_closing:
            return

        self.is_closing = True

        log.info("Initiating shutdown...")

        self._accepting_interactions = False

        # 1. Wait for active interactions
        await self.wait_for_interactions()

        # 2. Cancel background tasks
        if self._background_tasks:
            log.info("Cancelling %d background task(s)", len(self._background_tasks))
            for task in list(self._background_tasks):
                if not task.done():
                    task.cancel()

            await asyncio.wait(self._background_tasks, timeout=10.0)

        # 3. Close database
        try:
            await self.db.close()
            log.info("Database closed successfully")
        except Exception:
            log.exception("Error closing database")

        # 4. Let discord.py do its cleanup
        await super().close()
        log.info("Bot shutdown complete")

    async def wait_for_interactions(self) -> None:
        if self._active_interactions == 0:
            return

        log.info("Waiting for %d active interaction(s) to finish...", self._active_interactions)

        try:
            await asyncio.wait_for(
                self._interactions_idle.wait(),
                timeout=SHUTDOWN_TIMEOUT_SECONDS,
            )
        except TimeoutError:
            log.warning(
                "Timed out waiting for %d interaction(s); forcing shutdown",
                self._active_interactions,
            )

    async def safe_shutdown(self) -> None:
        if not self.is_closing:
            asyncio.create_task(self.close())


async def main():
    bot = RoyalSteward()

    # Add OS signal handlers
    async def handle_signal(sig):
        log.info(f"Received signal {sig.name}")
        await bot.safe_shutdown()

    if os.name == "posix":  # Linux / macOS
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, lambda s=sig: asyncio.create_task(handle_signal(s)))

    try:
        async with bot:
            await bot.start(TOKEN)
    except asyncio.CancelledError:
        log.info("Shutdown requested via cancellation")
    except Exception:
        log.error("Unexpected error during bot runtime", exc_info=True)
    finally:
        log.info("Main loop exited")


if __name__ == "__main__":
    asyncio.run(main())

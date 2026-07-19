import inspect
from contextlib import asynccontextmanager
import traceback
from logging import Logger
import discord
from config import DB_PATH
import aiosqlite
import logging

from models.ShownException import ShownException


from contextlib import asynccontextmanager
import logging

import discord


@asynccontextmanager
async def processing_response(
    interaction: discord.Interaction,
    *,
    show_processing: bool = True,
    ephemeral: bool = True,
    log: logging.Logger | None = None,
):
    logger = log or get_caller_logger(depth=2)
    owns_response = False

    if show_processing:
        await interaction.response.defer(
            thinking=True,
            ephemeral=ephemeral,
        )
        owns_response = True

    async def handle_error(**message) -> None:
        logger.exception(
            "Interaction failed: user=%s guild=%s channel=%s",
            interaction.user.id,
            interaction.guild_id,
            interaction.channel_id,
        )

        if owns_response:
            await interaction.edit_original_response(**message)
        elif not interaction.response.is_done():
            await interaction.response.send_message(
                ephemeral=ephemeral,
                **message,
            )
        else:
            await interaction.followup.send(
                ephemeral=ephemeral,
                **message,
            )

    try:
        yield

    except ShownException as error:
        await handle_error(**error.data)
        return

    except Exception:
        await handle_error(content="Unexpected error.")
        raise

    else:
        if not owns_response:
            return

        try:
            message = await interaction.original_response()

            if not message.content:
                await interaction.edit_original_response(content="Done.")

        except discord.NotFound:
            pass


def get_caller_logger(depth: int = 1) -> logging.Logger:
    frame = inspect.currentframe()

    try:
        caller = frame

        for _ in range(depth + 1):
            if caller is None:
                return logging.getLogger("__main__")

            caller = caller.f_back

        module_name = caller.f_globals.get("__name__", "__main__")
        return logging.getLogger(module_name)
    finally:
        del frame

@asynccontextmanager
async def connect():
    db = await aiosqlite.connect(DB_PATH)
    db.row_factory = aiosqlite.Row
    try:
        yield db
    finally:
        await db.close()

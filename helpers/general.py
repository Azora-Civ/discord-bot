from contextlib import asynccontextmanager
import traceback
from logging import Logger
import discord
from config import DB_PATH
import aiosqlite
import logging


@asynccontextmanager
async def processing_response(
    interaction: discord.Interaction,
    error_message: str = "Something went wrong.",
    ephemeral: bool = True,
    log: logging.Logger | None = None,
):
    log: Logger = log or logging.getLogger(__name__)
    await interaction.response.send_message("Processing...", ephemeral=ephemeral)

    try:
        yield
    except Exception:
        log.exception(
            "Interaction failed: user=%s guild=%s channel=%s",
            interaction.user.id if interaction.user else None,
            interaction.guild.id if interaction.guild else None,
            interaction.channel.id if interaction.channel else None,
        )

        await interaction.edit_original_response(content=error_message)
        raise


@asynccontextmanager
async def connect():
    db = await aiosqlite.connect(DB_PATH)
    db.row_factory = aiosqlite.Row
    try:
        yield db
    finally:
        await db.close()

from contextlib import asynccontextmanager
import traceback
import discord
from config import DB_PATH
import aiosqlite


@asynccontextmanager
async def processing_response(
    interaction: discord.Interaction,
    error_message: str = "Something went wrong.",
    ephemeral: bool = True,
):
    await interaction.response.send_message("Processing...", ephemeral=ephemeral)

    try:
        yield
    except Exception as e:
        traceback.print_exc()
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

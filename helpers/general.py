import inspect
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import discord

from models.ShownException import ShownException


@asynccontextmanager
async def respond(
    interaction: discord.Interaction,
    *,
    defer: bool = True,
    ephemeral: bool = True,
    logger: logging.Logger | None = None,
) -> AsyncIterator[bool]:
    bot = interaction.client
    logger = logger or get_caller_logger(depth=2)

    if not hasattr(bot, "interaction_lease"):
        raise RuntimeError("Interaction client does not support interaction leases.")

    with bot.interaction_lease() as accepted:
        if not accepted:
            await _respond(
                interaction,
                ephemeral=ephemeral,
                content="The bot is shutting down. Try again in a moment.",
            )
            yield False
            return

        deferred = False

        try:
            if defer:
                await interaction.response.defer(
                    thinking=True,
                    ephemeral=ephemeral,
                )
                deferred = True

            yield True

        except ShownException as error:
            logger.info("Interaction returned user-facing error: %s", error)
            await _respond(
                interaction,
                edit_original=deferred,
                ephemeral=ephemeral,
                **error.data,
            )

        except Exception:
            logger.exception("Interaction failed")
            await _respond(
                interaction,
                edit_original=deferred,
                ephemeral=ephemeral,
                content="Unexpected error.",
            )
            raise

        else:
            if deferred:
                await _complete_if_empty(interaction)


async def _respond(
    interaction: discord.Interaction,
    *,
    edit_original: bool = False,
    ephemeral: bool,
    **message: Any,
) -> None:
    if edit_original:
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


async def _complete_if_empty(
    interaction: discord.Interaction,
) -> None:
    try:
        message = await interaction.original_response()
    except discord.NotFound:
        return

    if not any(
        (
            message.content,
            message.embeds,
            message.attachments,
            message.components,
        )
    ):
        await interaction.edit_original_response(content="Done.")


def get_caller_logger(depth: int = 1) -> logging.Logger:
    frame = inspect.currentframe()

    try:
        caller = frame

        for _ in range(depth + 1):
            if caller is None:
                return logging.getLogger("__main__")

            caller = caller.f_back

        return logging.getLogger(caller.f_globals.get("__name__", "__main__"))
    finally:
        del frame

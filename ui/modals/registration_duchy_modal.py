import json
from dataclasses import asdict

import discord

import config as cfg
from helpers.general import respond
from models.duchy import Duchy


async def get_duchies(db) -> list[Duchy]:
    duchies_json = await db.key_values.get(key=cfg.REGISTRATION_DUCHY_KEY)

    if duchies_json:
        duchies = [Duchy(**duchy) for duchy in json.loads(duchies_json)]
    else:
        duchies = []

    return duchies

async def registration_duchy_modal(db):
    duchies = await get_duchies(db)

    return RegistrationDuchyModal(db, duchies)


class RegistrationDuchyModal(discord.ui.Modal, title="Duchy Entry"):
    def __init__(self, db, duchies: list[Duchy], **kwargs):
        discord.ui.Modal.__init__(self, **kwargs)

        self.db = db
        self.duchies.default = _encode(duchies)

    duchies = discord.ui.TextInput(
        label="Duchies and Cities",
        placeholder="Name | Role id | Emoji",
        style=discord.TextStyle.paragraph,
        required=False,
        max_length=4000,
    )

    async def on_submit(self, interaction: discord.Interaction) -> None:
        async with respond(interaction, defer=False) as should_process:
            if not should_process:
                return

            duchies, errors = _decode(self.duchies.value)
            errors.extend(_validate(duchies, interaction.guild))

            if errors:
                await interaction.response.send_message(
                    "Could not update duchies:\n" + "\n".join(f"- {error}" for error in errors),
                    ephemeral=True,
                )
                return

            await self.db.key_values.set(
                key=cfg.REGISTRATION_DUCHY_KEY,
                value=json.dumps([asdict(duchy) for duchy in duchies]),
            )

            await interaction.response.send_message(
                f"Updated {len(duchies)} duchies/cities.",
                ephemeral=True,
            )


def _encode(duchies: list[Duchy]) -> str:
    return "\n".join(
        f"{duchy.name} | {duchy.mention} | {duchy.emoji}"
        for duchy in duchies
    )


def _decode(duchies: str) -> tuple[list[Duchy], list[str]]:
    decoded: list[Duchy] = []
    errors: list[str] = []

    for line_number, raw_line in enumerate(duchies.splitlines(), start=1):
        line = raw_line.strip()
        if not line:
            continue

        parts = [part.strip() for part in line.split("|")]
        if len(parts) != 3:
            errors.append(
                f"Line {line_number} must use `Name | Role id | Emoji`."
            )
            continue

        name, mention, emoji = parts
        if not name:
            errors.append(f"Line {line_number} is missing a name.")
            continue

        decoded.append(Duchy(name=name, mention=mention, emoji=emoji))

    return decoded, errors


def _validate(duchies: list[Duchy], guild: discord.Guild | None) -> list[str]:
    if guild is None:
        return ["This command must be used in a server."]

    errors: list[str] = []
    seen_names: set[str] = set()

    for duchy in duchies:
        name_key = duchy.name.casefold()
        if name_key in seen_names:
            errors.append(f"`{duchy.name}` is listed more than once.")
        seen_names.add(name_key)

        if duchy.emoji and not _emoji_exists(duchy.emoji, guild):
            errors.append(f"`{duchy.name}` uses unknown emoji `{duchy.emoji}`.")

    return errors


def _emoji_exists(emoji: str, guild: discord.Guild) -> bool:
    partial = discord.PartialEmoji.from_str(emoji)

    if partial.id is None:
        return True

    return guild.get_emoji(partial.id) is not None

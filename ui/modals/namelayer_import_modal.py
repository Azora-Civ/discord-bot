import binascii
import zlib

import discord

from helpers.encoding import deflate_text, inflate_text
from helpers.general import respond
from models.permission import Permission, PermissionLevel
from models.ShownException import BadRequestException


class NameLayerImportModal(
    discord.ui.Modal,
    title="NameLayer membership import",
):
    info = discord.ui.TextDisplay(
        "Copy the text sequence below to clipboard and run the jsmacros script at the right position. "
        "Afterwards paste the results back."
    )

    macro_input = discord.ui.TextInput(
        label="jsmacros input, replace with output.",
        style=discord.TextStyle.paragraph,
        required=True,
        max_length=4000,
    )

    def __init__(self, namelayers: list[str]) -> None:
        super().__init__()

        macro_input = f"/search:{' '.join(namelayers)}"
        compressed_input = deflate_text(macro_input)

        # TextInput values must be configured on the instance.
        self.macro_input.default = compressed_input

    async def on_submit(self, interaction: discord.Interaction) -> None:
        async with respond(interaction) as should_process:
            if not should_process:
                return

            macro_output = self.macro_input.value
            entries = parse_results(macro_output)
            await interaction.client.permission_service.import_permissions(entries)
            await interaction.edit_original_response(content=f"Imported {len(entries)} permission entries.")


def parse_results(text: str) -> list[Permission]:
    results = []

    try:
        text = inflate_text(text)
    except (binascii.Error, UnicodeDecodeError, ValueError, zlib.error) as exc:
        raise BadRequestException("Import text is not valid compressed macro output.") from exc

    for line_number, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue

        parts = line.split("\t")

        if len(parts) != 3:
            raise BadRequestException(f"Invalid result on line {line_number}: {line!r}")

        namelayer, name, membership = (part.strip() for part in parts)
        try:
            level = PermissionLevel[membership.upper()]
        except KeyError as exc:
            raise BadRequestException(f"Invalid membership on line {line_number}: {membership!r}") from exc

        results.append(
            Permission(
                namelayer=namelayer,
                ign=name,
                level=level,
            )
        )

    return results


import discord

from helpers.deflate import deflate_text, inflate_text
from helpers.general import processing_response
from models.permission import Permission, PermissionLevel


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
        async with processing_response(interaction):
            macro_output = self.macro_input.value
            entries = parse_results(macro_output)
            await interaction.client.permission_service.import_permissions(entries)

def parse_results(text: str) -> list[Permission]:
    results = []

    text = inflate_text(text)

    for line_number, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue

        parts = line.split("\t")

        if len(parts) != 3:
            raise ValueError(
                f"Invalid result on line {line_number}: {line!r}"
            )

        namelayer, name, membership = parts
        results.append(Permission(
            namelayer=namelayer,
            ign=name,
            level=PermissionLevel[membership.upper()],
        ))

    return results

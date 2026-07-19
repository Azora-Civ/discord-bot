import json
from dataclasses import asdict

import discord

import config as cfg
from models.embed_config import EmbedConfig
from repositories.key_values import KeyValueRepository


class RegistrationEmbedModal(discord.ui.Modal, title="Edit registration embed"):
    embed_title = discord.ui.TextInput(
        label="Title",
        max_length=256,
    )

    description = discord.ui.TextInput(
        label="Description",
        style=discord.TextStyle.paragraph,
        max_length=4000,
    )

    colour = discord.ui.TextInput(
        label="Colour",
        placeholder="#5865F2",
        max_length=7,
    )

    footer = discord.ui.TextInput(
        label="Footer",
        required=False,
        max_length=2048,
    )

    image_urls = discord.ui.TextInput(
        label="Thumbnail URL|Image URL",
        required=False,
        max_length=2048,
    )

    def __init__(
        self,
        config: EmbedConfig
    ):
        super().__init__()

        self.config = config

        self.embed_title.default = config.title
        self.description.default = config.description
        self.colour.default = f"#{config.colour:06X}"
        self.footer.default = config.footer or ""
        self.image_urls.default = f"{config.thumbnail_url or ''}|{config.image_url or ''}"

    async def on_submit(self, interaction: discord.Interaction):
        try:
            colour = int(self.colour.value.removeprefix("#"), 16)
        except ValueError:
            await interaction.response.send_message(
                "The colour must look like `#5865F2`.",
                ephemeral=True,
            )
            return

        thumbnail_raw, separator, image_raw = self.image_urls.value.partition("|")

        thumbnail_url = thumbnail_raw.strip() or None
        image_url = image_raw.strip() or None

        config = EmbedConfig(
            title=self.embed_title.value,
            description=self.description.value,
            colour=colour,
            footer=self.footer.value or None,
            thumbnail_url=thumbnail_url,
            image_url=image_url,
        )

        await KeyValueRepository().set(key=cfg.REGISTRATION_EMBED_KEY, value=json.dumps(asdict(config)))

        await interaction.response.send_message(
            "Registration embed updated. New panels will use this instead.",
            embed=config.create_embed(),
            ephemeral=True,
        )
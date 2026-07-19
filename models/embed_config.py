from dataclasses import dataclass

import discord


@dataclass
class EmbedConfig:
    title: str
    description: str
    colour: int
    thumbnail_url: str | None = None
    image_url: str | None = None
    footer: str | None = None

    def create_embed(self) -> discord.Embed:
        embed = discord.Embed(
            title=self.title,
            description=self.description,
            colour=self.colour,
        )

        if self.thumbnail_url:
            embed.set_thumbnail(url=self.thumbnail_url)

        if self.image_url:
            embed.set_image(url=self.image_url)

        if self.footer:
            embed.set_footer(text=self.footer)

        return embed
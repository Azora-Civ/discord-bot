import discord

from ui.views.paginated_view import PaginationView


def paginated_panel(embeds: list[discord.Embed]) -> dict[str, object]:
    if len(embeds) == 0:
        return {}

    if len(embeds) == 1:
        return {
            "embed": embeds[0],
        }

    pv = PaginationView(embeds)

    return {"embed": embeds[0], "view": pv}

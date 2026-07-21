import discord
from discord import app_commands

MAX_CHOICES = 25


async def ign_autocomplete(
    interaction: discord.Interaction,
    current: str,
) -> list[app_commands.Choice[str]]:
    db = interaction.client.db
    citizens = await db.citizens.fetch_all()
    permissions = await db.permissions.fetch_all()
    permission_exceptions = await db.permission_exceptions.fetch_all()

    values = {
        citizen.in_game_name
        for citizen in citizens
    }
    values.update(permission.ign for permission in permissions)
    values.update(permission.ign for permission in permission_exceptions)

    return _choices(values, current)


async def namelayer_autocomplete(
    interaction: discord.Interaction,
    current: str,
) -> list[app_commands.Choice[str]]:
    db = interaction.client.db
    group_permissions = await db.group_permissions.fetch_all()
    permissions = await db.permissions.fetch_all()
    permission_exceptions = await db.permission_exceptions.fetch_all()

    values = {
        permission.namelayer
        for permission in group_permissions
    }
    values.update(permission.namelayer for permission in permissions)
    values.update(permission.namelayer for permission in permission_exceptions)

    return _choices(values, current)


async def track_autocomplete(
    interaction: discord.Interaction,
    current: str,
) -> list[app_commands.Choice[str]]:
    tracks = await interaction.client.db.role_tracks.fetch_all()
    return _choices((track.name for track in tracks), current)


def _choices(values, current: str) -> list[app_commands.Choice[str]]:
    current = current.casefold()
    matches = [
        value
        for value in values
        if not current or current in value.casefold()
    ]
    matches.sort(key=lambda value: (not value.casefold().startswith(current), value.casefold()))

    return [
        app_commands.Choice(name=value[:100], value=value[:100])
        for value in matches[:MAX_CHOICES]
    ]

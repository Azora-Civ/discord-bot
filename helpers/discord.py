from collections.abc import Sequence

import discord
from discord import Client, Guild, Member, Message, Role
from discord.ext.commands import Bot

import config as cfg


async def get_guild(client: Client) -> Guild:
    return client.get_guild(cfg.GUILD_ID) or await client.fetch_guild(cfg.GUILD_ID)


async def get_member(client, user_id: int) -> Member | None:
    guild = await get_guild(client)
    try:
        return guild.get_member(user_id) or await guild.fetch_member(user_id)
    except discord.NotFound:
        return None


async def get_members(client) -> Sequence[Member]:
    guild = await get_guild(client)
    return guild.members

async def get_guild_roles(client, user_ids: list[int]) -> Sequence[Role]:
    guild = await get_guild(client)
    members = await guild.query_members(
        user_ids=user_ids,
    )

    roles = set(role for member in members for role in member.roles)

    return list(roles)

async def get_message(client: Bot, channel_id: int, message_id: int) -> Message | None:
    try:
        channel = client.get_channel(channel_id) or await client.fetch_channel(channel_id)
        message = await channel.fetch_message(message_id)
        return message
    except discord.NotFound:
        return None

from typing import Sequence, List

from _testcapi import awaitType
from discord import Member, Guild, Role, Client
import asyncio
import discord
import config as cfg


async def get_guild(client: Client) -> Guild:
    id = cfg.GUILD_ID
    return client.get_guild(id) or await client.fetch_guild(id)


async def get_member(client, user_id: int) -> Member | None:
    guild = await get_guild(client)
    return guild.get_member(user_id) or await guild.fetch_member(user_id)


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

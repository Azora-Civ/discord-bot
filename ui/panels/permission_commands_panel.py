import discord
from discord import Client, Member

from helpers.permissions import (
    corrected_namelayer,
    resolve_permission_target,
    role_context_for_namelayer,
    role_context_for_user,
)
from ui.panels.paginated_panel import paginated_panel

MAX_COMMAND_BLOCK_LENGTH = 3500
MAX_COMMAND_PER_PAGE = 25

async def permission_command_embeds(
        client: Client,
        namelayer: str | None = None,
        ign: str | None = None,
        user: Member | None = None
) -> dict[str, object]:
    if namelayer is not None:
        namelayer = await corrected_namelayer(client, namelayer)

        role_member_igns_by_id, role_sources_by_id = await role_context_for_namelayer(
            client,
            namelayer,
        )
        return _permission_command_embeds(
            title=f"Commands to align '{namelayer}' namelayer",
            commands=await client.permission_service.get_namelayer_member_commands(
                namelayer,
                role_member_igns_by_id,
                role_sources_by_id,
            ),
        )

    ign, name = await resolve_permission_target(client, ign=ign, user=user)
    return _permission_command_embeds(
        title=f"Commands to align permissions for {name}",
        commands=await client.permission_service.get_user_permission_commands(
            ign,
            await role_context_for_user(client, ign),
        ),
    )


def _permission_command_embeds(title: str, commands: list[str]) -> dict[str, object]:
    if not commands:
        return paginated_panel([
            discord.Embed(
                title=title,
                description="No commands needed.",
                color=discord.Color.green(),
            )
        ])

    chunks = _chunk_commands(commands)
    total = len(chunks)

    return paginated_panel([
        discord.Embed(
            title=f"{title} ({index}/{total})" if total > 1 else title,
            description=f"{len(commands)} command(s):\n```{_join_commands(chunk)}```",
            color=discord.Color.blue(),
        )
        for index, chunk in enumerate(chunks, start=1)
    ])


def _chunk_commands(commands: list[str]) -> list[list[str]]:
    chunks: list[list[str]] = []
    current_chunk: list[str] = []
    current_length = 0
    current_count = 0

    for command in commands:
        current_length += len(command) + 11
        current_count += 1

        if current_chunk and (current_length > MAX_COMMAND_BLOCK_LENGTH or current_count > MAX_COMMAND_PER_PAGE):
            chunks.append(current_chunk)
            current_chunk = []
            current_length = 0
            current_count = 0

        current_chunk.append(command)


    if current_chunk:
        chunks.append(current_chunk)

    return chunks


def _join_commands(commands: list[str]) -> str:
    return "```\n```".join(commands)

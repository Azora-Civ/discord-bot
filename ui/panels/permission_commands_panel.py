import discord
from discord import Member, Client

from cogs.citizens_cog import ign_from_user
from models.ShownException import NotFoundException, BadRequestException
from repositories.group_permissions import GroupPermissionsRepository
from services.permission_service import PermissionService
from ui.panels.paginated_panel import paginated_panel

MAX_COMMAND_BLOCK_LENGTH = 3500
MAX_COMMAND_PER_PAGE = 25

async def permission_command_embeds(
        client: Client,
        namelayer: str | None = None,
        ign: str | None = None,
        user: Member | None = None
) -> dict[str, object]:
    service: PermissionService = client.get_cog("PermissionsCog").service

    if namelayer is not None:
        corrected_namelayer = await GroupPermissionsRepository().correct_namelayer(namelayer)
        if corrected_namelayer is None:
            raise NotFoundException("Couldn't find namelayer: {}!".format(namelayer))

        return _permission_command_embeds(
            title=f"Commands to align '{corrected_namelayer}' namelayer",
            commands=await service.get_namelayer_member_commands(corrected_namelayer),
        )

    if ign is None:
        if user is None:
            raise BadRequestException("Must pass either a role, ign or citizen.")

        ign = await ign_from_user(user)

    name = user.mention if user else ign
    return _permission_command_embeds(
        title=f"Commands to align permissions for {name}",
        commands=await service.get_user_permission_commands(ign),
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

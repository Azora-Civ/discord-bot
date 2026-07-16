import discord

MAX_COMMAND_BLOCK_LENGTH = 3500


def permission_command_embeds(title: str, commands: list[str]) -> list[discord.Embed]:
    if not commands:
        return [
            discord.Embed(
                title=title,
                description="No commands needed.",
                color=discord.Color.green(),
            )
        ]

    chunks = _chunk_commands(commands)
    total = len(chunks)

    return [
        discord.Embed(
            title=f"{title} ({index}/{total})" if total > 1 else title,
            description=f"{len(commands)} command(s):\n```text\n{_join_commands(chunk)}\n```",
            color=discord.Color.blue(),
        )
        for index, chunk in enumerate(chunks, start=1)
    ]


def _chunk_commands(commands: list[str]) -> list[list[str]]:
    chunks: list[list[str]] = []
    current_chunk: list[str] = []
    current_length = 0

    for command in commands:
        command_length = len(command) + 1
        if current_chunk and current_length + command_length > MAX_COMMAND_BLOCK_LENGTH:
            chunks.append(current_chunk)
            current_chunk = []
            current_length = 0

        current_chunk.append(command)
        current_length += command_length

    if current_chunk:
        chunks.append(current_chunk)

    return chunks


def _join_commands(commands: list[str]) -> str:
    return "\n".join(commands)

import discord
from discord import Member, app_commands
from discord.ext import commands

import config as cfg
from helpers.general import respond
from models.role_track import RoleTrack
from models.ShownException import BadRequestException, NotFoundException
from ui.panels.paginated_panel import paginated_panel

TRACKS_PAGE_SIZE = 10


class TracksCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    root_group = app_commands.Group(
        name="track",
        description="Commands for managing ordered role tracks.",
    )

    @root_group.command(
        name="set",
        description="[ADMIN] Set the ordered roles in a track.",
    )
    @app_commands.default_permissions(administrator=True)
    @app_commands.checks.has_permissions(administrator=True)
    async def set(
        self,
        interaction: discord.Interaction,
        name: str,
        role_1: discord.Role,
        role_2: discord.Role | None = None,
        role_3: discord.Role | None = None,
        role_4: discord.Role | None = None,
        role_5: discord.Role | None = None,
        role_6: discord.Role | None = None,
        role_7: discord.Role | None = None,
        role_8: discord.Role | None = None,
        role_9: discord.Role | None = None,
        role_10: discord.Role | None = None,
    ) -> None:
        async with respond(interaction, ephemeral=False) as should_process:
            if not should_process:
                return

            roles = [
                role
                for role in (role_1, role_2, role_3, role_4, role_5, role_6, role_7, role_8, role_9, role_10)
                if role
            ]
            if any(role.is_default() for role in roles):
                raise BadRequestException("A role track cannot contain @everyone.")
            if len({role.id for role in roles}) != len(roles):
                raise BadRequestException("A role can only appear once in a track.")

            track_name = name.strip()
            if not track_name:
                raise BadRequestException("Track name cannot be empty.")

            await self.bot.db.role_tracks.set(RoleTrack(name=track_name, role_ids=[role.id for role in roles]))

            await interaction.edit_original_response(
                content=None,
                embed=_track_embed(track_name, roles),
            )

    @root_group.command(
        name="list",
        description="[ADMIN] List configured role tracks.",
    )
    @app_commands.default_permissions(administrator=True)
    @app_commands.checks.has_permissions(administrator=True)
    async def list(self, interaction: discord.Interaction) -> None:
        async with respond(interaction) as should_process:
            if not should_process:
                return

            tracks = sorted(await self.bot.db.role_tracks.fetch_all(), key=lambda track: track.name.casefold())
            if not tracks:
                embed = discord.Embed(
                    title="Role Tracks",
                    description="No role tracks configured.",
                    color=discord.Color.blurple(),
                )
                await interaction.edit_original_response(content=None, embed=embed)
                return

            pages = []
            page_count = ((len(tracks) - 1) // TRACKS_PAGE_SIZE) + 1
            for index in range(0, len(tracks), TRACKS_PAGE_SIZE):
                page_tracks = tracks[index : index + TRACKS_PAGE_SIZE]
                page = (index // TRACKS_PAGE_SIZE) + 1
                embed = discord.Embed(title="Role Tracks", color=discord.Color.blurple())
                for track in page_tracks:
                    embed.add_field(
                        name=track.name,
                        value=_role_id_track_line(interaction.guild, track.role_ids),
                        inline=False,
                    )
                embed.set_footer(text=f"{len(tracks)} track(s) - Page {page}/{page_count}")
                pages.append(embed)

            msg = paginated_panel(pages)
            response = await interaction.edit_original_response(content=None, **msg)
            if view := msg.get("view"):
                view.message = response

    @root_group.command(
        name="promote",
        description="[ADMIN] Move a user to the next role in a track.",
    )
    @app_commands.default_permissions(administrator=True)
    @app_commands.checks.has_permissions(administrator=True)
    async def promote(self, interaction: discord.Interaction, name: str, user: Member) -> None:
        async with respond(interaction, ephemeral=False) as should_process:
            if not should_process:
                return

            track = await self._track(name)
            current_index = _current_track_index(track, user)
            if current_index is None:
                target_index = 0
            else:
                target_index = min(current_index + 1, len(track.role_ids) - 1)

            changed = await self._set_member_track_role(user, track, target_index)
            if not changed:
                await interaction.edit_original_response(
                    content=None,
                    embed=_movement_embed(
                        "Track Promotion",
                        f"{user.mention} is already at the top of `{track.name}`.",
                    ),
                )
                return

            await interaction.edit_original_response(
                content=None,
                embed=_movement_embed(
                    "Track Promotion",
                    f"Promoted {user.mention} to <@&{track.role_ids[target_index]}> in `{track.name}`.",
                ),
            )

    @root_group.command(
        name="demote",
        description="[ADMIN] Move a user to the previous role in a track.",
    )
    @app_commands.default_permissions(administrator=True)
    @app_commands.checks.has_permissions(administrator=True)
    async def demote(self, interaction: discord.Interaction, name: str, user: Member) -> None:
        async with respond(interaction, ephemeral=False) as should_process:
            if not should_process:
                return

            track = await self._track(name)
            current_index = _current_track_index(track, user)
            if current_index is None:
                await interaction.edit_original_response(
                    content=None,
                    embed=_movement_embed("Track Demotion", f"{user.mention} is not on `{track.name}`."),
                )
                return

            target_index = current_index - 1 if current_index > 0 else None
            changed = await self._set_member_track_role(user, track, target_index)
            if target_index is None:
                await interaction.edit_original_response(
                    content=None,
                    embed=_movement_embed("Track Demotion", f"Removed {user.mention} from `{track.name}`."),
                )
                return

            if not changed:
                await interaction.edit_original_response(
                    content=None,
                    embed=_movement_embed(
                        "Track Demotion",
                        f"{user.mention} is already at <@&{track.role_ids[target_index]}> in `{track.name}`.",
                    ),
                )
                return

            await interaction.edit_original_response(
                content=None,
                embed=_movement_embed(
                    "Track Demotion",
                    f"Demoted {user.mention} to <@&{track.role_ids[target_index]}> in `{track.name}`.",
                ),
            )

    async def _track(self, name: str) -> RoleTrack:
        track = await self.bot.db.role_tracks.find_by_name(name.strip())
        if track is None:
            raise NotFoundException(f"Couldn't find track: {name}.")
        return track

    async def _set_member_track_role(
        self,
        user: Member,
        track: RoleTrack,
        target_index: int | None,
    ) -> bool:
        target_role_id = track.role_ids[target_index] if target_index is not None else None
        current_role_ids = {role.id for role in user.roles}
        track_role_ids = set(track.role_ids)
        roles_to_remove = [
            role for role in user.roles if role.id in track_role_ids and role.id != target_role_id
        ]
        role_to_add = (
            user.guild.get_role(target_role_id)
            if target_role_id is not None and target_role_id not in current_role_ids
            else None
        )

        if target_role_id is not None and user.guild.get_role(target_role_id) is None:
            raise BadRequestException(f"Track `{track.name}` contains a deleted role: {target_role_id}.")

        if roles_to_remove:
            await user.remove_roles(*roles_to_remove, reason=f"Role track {track.name}")
        if role_to_add is not None:
            await user.add_roles(role_to_add, reason=f"Role track {track.name}")

        return bool(roles_to_remove or role_to_add)


def _current_track_index(track: RoleTrack, user: Member) -> int | None:
    role_ids = {role.id for role in user.roles}
    indexes = [index for index, role_id in enumerate(track.role_ids) if role_id in role_ids]
    return max(indexes) if indexes else None


def _track_embed(track_name: str, roles: list[discord.Role]) -> discord.Embed:
    embed = discord.Embed(
        title=f"Track: {track_name}",
        description=" -> ".join(role.mention for role in roles),
        color=discord.Color.blurple(),
    )
    embed.set_footer(text=f"{len(roles)} role(s)")
    return embed


def _role_id_track_line(guild: discord.Guild | None, role_ids: list[int]) -> str:
    return " -> ".join(_role_mention(guild, role_id) for role_id in role_ids)


def _role_mention(guild: discord.Guild | None, role_id: int) -> str:
    if guild is not None and guild.get_role(role_id) is None:
        return f"Deleted role ({role_id})"

    return f"<@&{role_id}>"


def _movement_embed(title: str, description: str) -> discord.Embed:
    return discord.Embed(
        title=title,
        description=description,
        color=discord.Color.blurple(),
    )


async def setup(bot: commands.Bot):
    await bot.add_cog(TracksCog(bot), guild=cfg.GUILD)

import logging
import re

import discord
from discord import app_commands
from discord.ext import commands

import config as cfg
from helpers.citizens import sync_citizen_member
from helpers.general import respond
from services.events import CitizenChangedEvent, CitizenChangeKind
from ui.panels.citizens_panel import citizen_list_panel, citizen_panel, citizen_stats_panel
from ui.views.citizen_management_view import CitizenManagementView

log = logging.getLogger(__name__)
SNITCH_HIT_REGEX = re.compile(r"`\[[^\]]+\]`\s+\*\*(.+?)\*\*\s+is at\s+.+")


class CitizensCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.service = bot.citizen_service
        self.service.on_citizen_changed.subscribe(self.handle_citizen_changed)
        self.snitch_cache = False
        self.snitch_channel: int | None = None

    async def handle_citizen_changed(self, event: CitizenChangedEvent) -> None:
        if event.kind == CitizenChangeKind.ACTIVITY:
            return

        if event.previous and event.previous.user_id != event.citizen.user_id:
            await sync_citizen_member(self.bot, event.previous.user_id, None, log=log)

        citizen = None if event.kind == CitizenChangeKind.DELETED else event.citizen
        await sync_citizen_member(self.bot, event.citizen.user_id, citizen, log=log)

    root_group = app_commands.Group(
        name="citizens",
        description="Commands for viewing and managing citizens.",
    )

    async def _set_snitch_channel(self):
        self.snitch_cache = True
        self.snitch_channel = await self.bot.db.key_values.get_int(
            key=cfg.CITIZEN_SNITCH_CHANNEL_ID_KEY
        )

    async def _is_mod(self, interaction: discord.Interaction) -> bool:
        if not isinstance(interaction.user, discord.Member):
            return False

        if interaction.user.guild_permissions.administrator:
            return True

        role_id = await self.bot.db.key_values.get_int(cfg.CITIZEN_MOD_ROLE_ID_KEY)
        return role_id is not None and any(role.id == role_id for role in interaction.user.roles)

    @root_group.command(
        name="list",
        description="List citizens, optionally filtering by in-game name.",
    )
    @app_commands.describe(
        last_online_days="Only show citizens seen online within this many days.",
    )
    async def list(
        self,
        interaction: discord.Interaction,
        ign: str | None = None,
        last_online_days: app_commands.Range[int, 1, 3650] | None = None,
    ):
        async with respond(interaction) as should_process:
            if not should_process:
                return

            citizens = await self.service.list_citizens(
                ign,
                last_online_days=last_online_days,
            )
            msg = citizen_list_panel(
                citizens,
                ign_filter=ign,
                last_online_days=last_online_days,
                author_id=interaction.user.id,
            )
            response = await interaction.edit_original_response(content=None, **msg)
            if view := msg.get("view"):
                view.message = response

    @root_group.command(
        name="view",
        description="View one citizen by Discord user or in-game name.",
    )
    async def view(
        self,
        interaction: discord.Interaction,
        user: discord.Member | None = None,
        ign: str | None = None,
    ):
        async with respond(interaction) as should_process:
            if not should_process:
                return

            if user is None and ign is None:
                user = interaction.user

            citizen = await self.service.get_citizen(user_id=user.id if user else None, ign=ign)
            msg = {"embed": citizen_panel(citizen)}
            if await self._is_mod(interaction):
                msg["view"] = CitizenManagementView(citizen)
            await interaction.edit_original_response(content=None, **msg)

    @root_group.command(
        name="stats",
        description="Show citizen totals and activity stats.",
    )
    async def stats(
        self,
        interaction: discord.Interaction,
        active_days: app_commands.Range[int, 1, 365] = 14,
    ):
        async with respond(interaction) as should_process:
            if not should_process:
                return

            total, active = await self.service.stats(active_days)
            await interaction.edit_original_response(
                content=None,
                embed=citizen_stats_panel(total, active, active_days),
            )

    @root_group.command(
        name="set-snitch-channel",
        description="[ADMIN] Set the channel used to track citizen activity from snitch hits.",
    )
    @app_commands.default_permissions(administrator=True)
    @app_commands.checks.has_permissions(administrator=True)
    async def set_snitch_channel(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel,
    ):
        async with respond(interaction, ephemeral=False) as should_process:
            if not should_process:
                return

            await self.bot.db.key_values.set_int(
                key=cfg.CITIZEN_SNITCH_CHANNEL_ID_KEY,
                value=channel.id,
            )
            await self._set_snitch_channel()
            await interaction.edit_original_response(
                content=(
                    "Citizen activity will now be tracked from snitch hits "
                    f"in {channel.mention}."
                )
            )

    @root_group.command(
        name="set-mod-role",
        description="[ADMIN] Set the role allowed to manage citizens.",
    )
    @app_commands.default_permissions(administrator=True)
    @app_commands.checks.has_permissions(administrator=True)
    async def set_mod_role(
        self,
        interaction: discord.Interaction,
        role: discord.Role | None = None,
    ):
        async with respond(interaction, ephemeral=False) as should_process:
            if not should_process:
                return

            if role is None:
                await self.bot.db.key_values.delete(cfg.CITIZEN_MOD_ROLE_ID_KEY)
                await interaction.edit_original_response(
                    content="Citizen mod role cleared. Administrators can still manage citizens."
                )
                return

            await self.bot.db.key_values.set_int(cfg.CITIZEN_MOD_ROLE_ID_KEY, role.id)
            await interaction.edit_original_response(
                content=f"Citizen mod role set to {role.mention}."
            )

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if not self.snitch_cache:
            await self._set_snitch_channel()

        if self.snitch_channel is None or message.channel.id != self.snitch_channel:
            return

        match = SNITCH_HIT_REGEX.search(message.content)
        if match:
            ign = match.group(1)
            await self.service.hit_snitch(ign)


async def setup(bot: commands.Bot):
    await bot.add_cog(CitizensCog(bot), guild=cfg.GUILD)

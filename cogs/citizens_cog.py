import logging
import re

import discord
from discord import app_commands
from discord.ext import commands

import config as cfg
from helpers.citizens import sync_citizen_member
from helpers.discord import is_mod
from helpers.general import respond
from models.citizen import Citizen, Citizenship
from models.ShownException import BadRequestException
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

    async def handle_citizen_changed(self, event: CitizenChangedEvent) -> None:
        if event.kind == CitizenChangeKind.ACTIVITY:
            return

        if event.previous and event.previous.user_id != event.citizen.user_id:
            await sync_citizen_member(self.bot, event.previous.user_id, None, log=log)

        citizen = None if event.kind == CitizenChangeKind.DELETED else event.citizen
        await sync_citizen_member(
            self.bot,
            event.citizen.user_id,
            citizen,
            log=log,
            sync_nickname=event.kind == CitizenChangeKind.CREATED and event.source == "registration_accepted",
        )

    root_group = app_commands.Group(
        name="citizens",
        description="Commands for viewing and managing citizens.",
    )

    @root_group.command(
        name="list",
        description="List citizens, optionally filtering by in-game name.",
    )
    @app_commands.describe(
        ign="Only show citizens whose in-game name contains this text.",
        last_online_days="Only show citizens seen online within this many days.",
        has_discord="Only show citizens with or without a linked Discord user.",
    )
    async def list(
        self,
        interaction: discord.Interaction,
        ign: str | None = None,
        last_online_days: app_commands.Range[int, 1, 3650] | None = None,
        has_discord: bool | None = None,
    ):
        async with respond(interaction) as should_process:
            if not should_process:
                return

            citizens = await self.service.list_citizens(
                ign,
                last_online_days=last_online_days,
                has_discord=has_discord,
            )
            msg = citizen_list_panel(
                citizens,
                ign_filter=ign,
                last_online_days=last_online_days,
                has_discord=has_discord,
                author_id=interaction.user.id,
            )
            response = await interaction.edit_original_response(content=None, **msg)
            if view := msg.get("view"):
                view.message = response

    @root_group.command(
        name="add",
        description="[MOD] Add a citizen or resident without a registration.",
    )
    @app_commands.describe(
        ign="In-game name for the new citizen/resident.",
        citizenship="Citizenship type to assign.",
        user="Optional Discord user to link.",
    )
    async def add(
        self,
        interaction: discord.Interaction,
        ign: str,
        citizenship: Citizenship,
        user: discord.Member | None = None,
    ):
        async with respond(interaction, ephemeral=False) as should_process:
            if not should_process:
                return

            if not await is_mod(interaction):
                raise BadRequestException("You are not permitted to add citizens.")

            citizen = await self.service.create_citizen(
                Citizen(
                    in_game_name=ign,
                    user_id=user.id if user is not None else None,
                    citizenship=citizenship,
                ),
                source="citizen_added_directly",
            )
            await interaction.edit_original_response(
                content=f"Added `{citizen.in_game_name}`.",
                embed=citizen_panel(citizen),
                view=CitizenManagementView(citizen),
            )

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
            if await is_mod(interaction):
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
        async with respond(interaction, ephemeral=False) as should_process:
            if not should_process:
                return

            total, active = await self.service.stats(active_days)
            await interaction.edit_original_response(
                content=None,
                embed=citizen_stats_panel(total, active, active_days),
            )

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.id != cfg.KIRA_USER_ID:
            return

        match = SNITCH_HIT_REGEX.search(message.content)
        if match:
            ign = match.group(1)
            await self.service.hit_snitch(ign)


async def setup(bot: commands.Bot):
    await bot.add_cog(CitizensCog(bot), guild=cfg.GUILD)

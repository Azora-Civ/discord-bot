import logging
import re
import time

import discord
from discord import app_commands
from discord.ext import commands, tasks

import config as cfg
from helpers.autocomplete import farm_autocomplete
from helpers.discord import get_message
from helpers.general import respond
from models.farm import Farm
from models.ShownException import BadRequestException, NotFoundException, UnauthorizedException
from ui.panels.farms_panel import farm_embed, panel_embed

log = logging.getLogger(__name__)

FARM_EVENT_REGEX = re.compile(
    r"\*\*\[([^\]]+)\]\*\*.*?\b(started|finished)\s+farming:\s*(.+)",
    re.IGNORECASE,
)
PANEL_REFRESH_SECONDS = 60


class FarmTrackCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def cog_load(self) -> None:
        self.update_panel.start()

    def cog_unload(self) -> None:
        self.update_panel.cancel()

    root_group = app_commands.Group(
        name="farms",
        description="Commands for tracking farms.",
    )

    @root_group.command(
        name="set",
        description="[FARMERS MOD] Set or delete a farm. Passing only name deletes it.",
    )
    @app_commands.describe(
        name="Farm name.",
        posxyz="Farm position, for example: 123 64 -456.",
        regrow_time="Regrow interval, for example: 12h 35m, 90m, or 30m 2h.",
        farm_time="Expected farming duration, for example: 30m.",
    )
    @app_commands.autocomplete(name=farm_autocomplete)
    async def set(
        self,
        interaction: discord.Interaction,
        name: str,
        posxyz: str | None = None,
        regrow_time: str | None = None,
        farm_time: str | None = None,
    ) -> None:
        async with respond(interaction, ephemeral=False) as should_process:
            if not should_process:
                return

            await self._require_farmers_mod(interaction)

            farm_name = _clean_name(name)
            if posxyz is None and regrow_time is None and farm_time is None:
                deleted = await self.bot.db.farms.delete_by_name(farm_name)
                if not deleted:
                    raise NotFoundException(f"Couldn't find farm: {farm_name}.")

                await self._refresh_panel_after_change()
                await interaction.edit_original_response(content=f"Deleted farm `{farm_name}`.")
                return

            existing_farm = await self.bot.db.farms.find_by_name(farm_name)
            if existing_farm is None and (posxyz is None or regrow_time is None or farm_time is None):
                raise BadRequestException(
                    "New farms require posxyz, regrow_time, and farm_time. Existing farms can be updated partially."
                )

            farm = Farm(
                name=farm_name,
                posxyz=posxyz.strip() if posxyz is not None else existing_farm.posxyz,
                regrow_time=_parse_interval(regrow_time) if regrow_time is not None else existing_farm.regrow_time,
                farm_time=_parse_interval(farm_time) if farm_time is not None else existing_farm.farm_time,
                started_time=existing_farm.started_time if existing_farm is not None else None,
                finished_time=existing_farm.finished_time if existing_farm is not None else None,
                additional_data=existing_farm.additional_data if existing_farm is not None else {},
            )

            if not farm.posxyz:
                raise BadRequestException("Farm position cannot be empty.")

            await self.bot.db.farms.set(farm)
            saved = await self.bot.db.farms.find_by_name(farm.name)

            await self._refresh_panel_after_change()
            await interaction.edit_original_response(
                content=None,
                embed=farm_embed(saved or farm),
            )

    @root_group.command(
        name="set_farmers_mod",
        description="[ADMIN] Set the role permitted to make farm changes.",
    )
    @app_commands.default_permissions(administrator=True)
    @app_commands.checks.has_permissions(administrator=True)
    async def set_farmers_mod(
        self,
        interaction: discord.Interaction,
        role: discord.Role,
    ) -> None:
        async with respond(interaction, ephemeral=False) as should_process:
            if not should_process:
                return

            if role.is_default():
                raise BadRequestException("@everyone cannot be the farmers mod role.")

            await self.bot.db.key_values.set_int(cfg.FARMS_MOD_ROLE_ID_KEY, role.id)
            await interaction.edit_original_response(
                content=f"Farm changes can now be made by users with {role.mention}.",
            )

    @root_group.command(
        name="view",
        description="View a tracked farm.",
    )
    @app_commands.describe(name="Farm name.")
    @app_commands.autocomplete(name=farm_autocomplete)
    async def view(
        self,
        interaction: discord.Interaction,
        name: str,
    ) -> None:
        async with respond(interaction) as should_process:
            if not should_process:
                return

            farm = await self._farm(name)
            await interaction.edit_original_response(content=None, embed=farm_embed(farm))

    @root_group.command(
        name="panel",
        description="[ADMIN] Create or replace the live farms panel in this channel.",
    )
    @app_commands.default_permissions(administrator=True)
    @app_commands.checks.has_permissions(administrator=True)
    async def panel(self, interaction: discord.Interaction) -> None:
        async with respond(interaction, ephemeral=True) as should_process:
            if not should_process:
                return

            if interaction.channel is None:
                raise BadRequestException("This command must be used in a channel.")

            message = await interaction.channel.send(embed=await panel_embed(self.bot))
            await self.bot.db.key_values.set_int(cfg.FARMS_PANEL_CHANNEL_ID_KEY, message.channel.id)
            await self.bot.db.key_values.set_int(cfg.FARMS_PANEL_MESSAGE_ID_KEY, message.id)

            await interaction.edit_original_response(content="Farm panel posted.")

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if message.author.id != cfg.KIRA_USER_ID:
            return

        event = _farm_event_from_message(message.content)
        if event is None:
            return

        action, farm_name, player_name = event
        now = int(time.time())

        if action == "started":
            updated = await self.bot.db.farms.update_started_time(farm_name, now, last_farmed_by=player_name)
        else:
            updated = await self.bot.db.farms.update_finished_time(farm_name, now, last_farmed_by=player_name)

        if not updated:
            log.info("Ignored Kira farm event for unknown farm: %s", farm_name)
            return

        await self._refresh_panel_after_change()

    @tasks.loop(seconds=PANEL_REFRESH_SECONDS)
    async def update_panel(self) -> None:
        await self._refresh_panel_after_change()

    @update_panel.before_loop
    async def before_update_panel(self) -> None:
        await self.bot.wait_until_ready()

    async def _farm(self, name: str) -> Farm:
        farm_name = _clean_name(name)
        farm = await self.bot.db.farms.find_by_name(farm_name)
        if farm is None:
            raise NotFoundException(f"Couldn't find farm: {farm_name}.")
        return farm

    async def _require_farmers_mod(self, interaction: discord.Interaction) -> None:
        user = interaction.user
        if not isinstance(user, discord.Member):
            raise UnauthorizedException("This command must be used in a guild.")

        if user.guild_permissions.administrator:
            return

        role_id = await self.bot.db.key_values.get_int(cfg.FARMS_MOD_ROLE_ID_KEY)
        if role_id is not None and any(role.id == role_id for role in user.roles):
            return

        raise UnauthorizedException("You are not permitted to change farms.")

    async def _refresh_panel_after_change(self) -> None:
        channel_id = await self.bot.db.key_values.get_int(cfg.FARMS_PANEL_CHANNEL_ID_KEY)
        message_id = await self.bot.db.key_values.get_int(cfg.FARMS_PANEL_MESSAGE_ID_KEY)
        if channel_id is None or message_id is None:
            return

        message = await get_message(self.bot, channel_id, message_id)
        if message is None:
            await self.bot.db.key_values.delete(cfg.FARMS_PANEL_CHANNEL_ID_KEY)
            await self.bot.db.key_values.delete(cfg.FARMS_PANEL_MESSAGE_ID_KEY)
            return

        await message.edit(embed=await panel_embed(self.bot))


def _clean_name(name: str) -> str:
    cleaned = name.strip().strip("`")
    if not cleaned:
        raise BadRequestException("Farm name cannot be empty.")
    return cleaned


def _farm_event_from_message(content: str) -> tuple[str, str, str | None] | None:
    if match := FARM_EVENT_REGEX.search(content):
        return match.group(2).lower(), _clean_name(match.group(3)), match.group(1).strip()

    return None


def _parse_interval(value: str) -> int:
    total_seconds = 0
    parts = value.lower().split()
    if not parts:
        raise BadRequestException("Time intervals cannot be empty.")

    for part in parts:
        unit = part[-1]
        amount = part[:-1]
        if unit not in {"h", "m"} or not amount:
            raise BadRequestException(f"Invalid time interval part: `{part}`.")

        try:
            parsed_amount = int(amount)
        except ValueError as exc:
            raise BadRequestException(f"Invalid time interval amount: `{part}`.") from exc

        if parsed_amount <= 0:
            raise BadRequestException(f"Time interval amounts must be positive: `{part}`.")

        if unit == "h":
            total_seconds += parsed_amount * 60 * 60
        else:
            total_seconds += parsed_amount * 60

    return total_seconds


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(FarmTrackCog(bot), guild=cfg.GUILD)

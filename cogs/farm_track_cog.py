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
from ui.panels.farms_panel import farm_embed, layered_farm_embed, panel_embed

log = logging.getLogger(__name__)

FARM_EVENT_REGEX = re.compile(
    r"\*\*\[([^\]]+)\]\*\*.*?\b(started|finished):\s*(.+)",
    re.IGNORECASE,
)
KIRA_PLAYER_REGEX = re.compile(r"\*\*\[([^\]]+)\]\*\*")
KIRA_PUBLIC_PING_PLACEHOLDER = "<@!>"
KIRA_PRIVATE_PING_PLACEHOLDER = "<@!p>"
FARM_LAYER_REGEX = re.compile(r"^(?P<base>.+?)\s+L(?P<layer>\d+)$", re.IGNORECASE)
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
        requirements="Optional farming requirements.",
        info="Optional farm info.",
        layers="Optional number of farm layers to create or keep.",
    )
    @app_commands.autocomplete(name=farm_autocomplete)
    async def set(
        self,
        interaction: discord.Interaction,
        name: str,
        posxyz: str | None = None,
        regrow_time: str | None = None,
        farm_time: str | None = None,
        requirements: str | None = None,
        info: str | None = None,
        layers: int | None = None,
    ) -> None:
        async with respond(interaction, ephemeral=False) as should_process:
            if not should_process:
                return

            await self._require_farmers_mod(interaction)

            farm_name = _clean_name(name)
            if layers is not None:
                if layers < 0:
                    raise BadRequestException("Layer count cannot be negative.")

                base_name, changed_count, deleted_count = await self._set_layered_farms(
                    farm_name,
                    layers,
                    posxyz=posxyz,
                    regrow_time=regrow_time,
                    farm_time=farm_time,
                    requirements=requirements,
                    info=info,
                )
                await self._refresh_panel_after_change()
                if layers == 0:
                    await interaction.edit_original_response(
                        content=f"Deleted all `{base_name}` layers ({deleted_count} deleted).",
                    )
                    return

                await interaction.edit_original_response(
                    content=f"Set `{base_name}` layers L1-L{layers} ({changed_count} saved, {deleted_count} deleted).",
                )
                return

            if all(value is None for value in (posxyz, regrow_time, farm_time, requirements, info)):
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

            additional_data = dict(existing_farm.additional_data) if existing_farm is not None else {}
            _set_optional_text(additional_data, "requirements", requirements)
            _set_optional_text(additional_data, "info", info)

            farm = Farm(
                name=farm_name,
                posxyz=posxyz.strip() if posxyz is not None else existing_farm.posxyz,
                regrow_time=_parse_interval(regrow_time) if regrow_time is not None else existing_farm.regrow_time,
                farm_time=_parse_interval(farm_time) if farm_time is not None else existing_farm.farm_time,
                started_time=existing_farm.started_time if existing_farm is not None else None,
                finished_time=existing_farm.finished_time if existing_farm is not None else None,
                additional_data=additional_data,
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

    async def _set_layered_farms(
        self,
        farm_name: str,
        layers: int,
        *,
        posxyz: str | None,
        regrow_time: str | None,
        farm_time: str | None,
        requirements: str | None,
        info: str | None,
    ) -> tuple[str, int, int]:
        base_name, _ = _farm_layer(farm_name)
        existing_farms = await self.bot.db.farms.fetch_all()
        existing_by_name = {farm.name.casefold(): farm for farm in existing_farms}
        existing_layers = [
            (layer, farm)
            for farm in existing_farms
            for parsed_base, layer in [_farm_layer(farm.name)]
            if layer is not None and parsed_base.casefold() == base_name.casefold()
        ]

        if layers == 0:
            deleted_count = 0
            for _, farm in existing_layers:
                if await self.bot.db.farms.delete_by_name(farm.name):
                    deleted_count += 1

            if await self.bot.db.farms.delete_by_name(base_name):
                deleted_count += 1

            return base_name, 0, deleted_count

        template = (
            existing_by_name.get(farm_name.casefold())
            or existing_by_name.get(base_name.casefold())
            or existing_by_name.get(_layer_name(base_name, 1).casefold())
            or next((farm for _, farm in sorted(existing_layers, key=lambda item: item[0])), None)
        )

        if template is None and (posxyz is None or regrow_time is None or farm_time is None):
            raise BadRequestException(
                "New layered farms require posxyz, regrow_time, and farm_time. "
                "Existing layered farms can be updated partially."
            )

        layer_posxyz = posxyz.strip() if posxyz is not None else template.posxyz
        if not layer_posxyz:
            raise BadRequestException("Farm position cannot be empty.")

        layer_regrow_time = _parse_interval(regrow_time) if regrow_time is not None else template.regrow_time
        layer_farm_time = _parse_interval(farm_time) if farm_time is not None else template.farm_time
        additional_data = dict(template.additional_data) if template is not None else {}
        _set_optional_text(additional_data, "requirements", requirements)
        _set_optional_text(additional_data, "info", info)

        changed_count = 0
        for layer in range(1, layers + 1):
            layer_name = _layer_name(base_name, layer)
            existing_layer = existing_by_name.get(layer_name.casefold())
            state_source = existing_layer or template
            farm = Farm(
                name=layer_name,
                posxyz=layer_posxyz,
                regrow_time=layer_regrow_time,
                farm_time=layer_farm_time,
                started_time=state_source.started_time if state_source is not None else None,
                finished_time=state_source.finished_time if state_source is not None else None,
                additional_data=additional_data,
            )
            await self.bot.db.farms.set(farm)
            changed_count += 1

        deleted_count = 0
        for layer, farm in existing_layers:
            if layer > layers and await self.bot.db.farms.delete_by_name(farm.name):
                deleted_count += 1

        if await self.bot.db.farms.delete_by_name(base_name):
            deleted_count += 1

        return base_name, changed_count, deleted_count

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

            base_name, layered_farms = await self._farms_for_view(name)
            embed = (
                layered_farm_embed(base_name, layered_farms)
                if len(layered_farms) > 1
                else farm_embed(layered_farms[0][1])
            )
            await interaction.edit_original_response(content=None, embed=embed)

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

        await self._relay_kira_ping(message)

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

    async def _relay_kira_ping(self, message: discord.Message) -> None:
        if not _has_kira_ping_placeholder(message.content):
            return

        player_name = _player_name_from_message(message.content)
        citizen = await self.bot.db.citizens.fetch_by_ign(player_name) if player_name is not None else None
        if not await _delete_kira_ping_message(message):
            return

        if citizen is None or citizen.user_id is None:
            log.info("Deleted Kira ping for unknown or unlinked citizen: %s", player_name or "unknown")
            return

        relay_content = _replace_kira_ping_placeholder(message.content, citizen.user_id)
        allowed_mentions = discord.AllowedMentions(everyone=False, roles=False, users=True)

        try:
            if KIRA_PRIVATE_PING_PLACEHOLDER in message.content:
                user = self.bot.get_user(citizen.user_id) or await self.bot.fetch_user(citizen.user_id)
                await user.send(relay_content, allowed_mentions=allowed_mentions)
                return

            await message.channel.send(relay_content, allowed_mentions=allowed_mentions)
        except discord.HTTPException:
            log.exception("Failed to relay Kira ping for citizen: %s", player_name)

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

    async def _farms_for_view(self, name: str) -> tuple[str, list[tuple[int, Farm]]]:
        farm_name = _clean_name(name)
        base_name, parsed_layer = _farm_layer(farm_name)
        farms = await self.bot.db.farms.fetch_all()
        layers = [
            (layer, farm)
            for farm in farms
            for parsed_base, layer in [_farm_layer(farm.name)]
            if layer is not None and parsed_base.casefold() == base_name.casefold()
        ]
        if layers:
            return base_name, sorted(layers, key=lambda item: item[0])

        farm = await self.bot.db.farms.find_by_name(farm_name)
        if farm is None:
            raise NotFoundException(f"Couldn't find farm: {farm_name}.")

        return base_name, [(parsed_layer or 1, farm)]

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


def _farm_layer(name: str) -> tuple[str, int | None]:
    if match := FARM_LAYER_REGEX.match(name.strip()):
        return match.group("base").strip(), int(match.group("layer"))

    return name, None


def _layer_name(base_name: str, layer: int) -> str:
    return f"{base_name} L{layer}"


def _set_optional_text(data: dict[str, object], key: str, value: str | None) -> None:
    if value is None:
        return

    cleaned = value.strip()
    if cleaned:
        data[key] = cleaned
    else:
        data.pop(key, None)


def _farm_event_from_message(content: str) -> tuple[str, str, str | None] | None:
    if match := FARM_EVENT_REGEX.search(content):
        return match.group(2).lower(), _clean_name(match.group(3)), match.group(1).strip()

    return None


def _has_kira_ping_placeholder(content: str) -> bool:
    return KIRA_PUBLIC_PING_PLACEHOLDER in content or KIRA_PRIVATE_PING_PLACEHOLDER in content


def _player_name_from_message(content: str) -> str | None:
    if match := KIRA_PLAYER_REGEX.search(content):
        return match.group(1).strip()

    return None


def _replace_kira_ping_placeholder(content: str, user_id: int) -> str:
    mention = f"<@{user_id}>"
    return content.replace(KIRA_PRIVATE_PING_PLACEHOLDER, mention).replace(KIRA_PUBLIC_PING_PLACEHOLDER, mention)


async def _delete_kira_ping_message(message: discord.Message) -> bool:
    try:
        await message.delete()
    except discord.NotFound:
        return True
    except discord.Forbidden:
        log.exception("Missing permissions to delete Kira ping message: %s", message.id)
        return False
    except discord.HTTPException:
        log.exception("Failed to delete Kira ping message: %s", message.id)
        return False

    return True


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

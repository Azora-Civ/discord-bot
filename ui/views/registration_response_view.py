import discord

from config import CITIZEN_MOD_ROLE_ID_KEY
from helpers.general import respond
from models.citizen import Citizen
from models.ShownException import BadRequestException, BadStateException
from ui.modals.citizen_application_modal import citizen_application_modal
from ui.panels.permission_commands_panel import permission_command_embeds


class RegistrationResponseView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Accept",
        emoji="✅",
        style=discord.ButtonStyle.primary,
        custom_id="registration_response_view:accept_citizen",
    )
    async def accept_citizen(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):
        async with respond(interaction) as should_process:
            if not should_process:
                return

            if not await _is_mod(interaction):
                raise BadRequestException("You are not permitted to accept the registration.")

            registration = await _get_registration(interaction)
            cog = interaction.client.get_cog("RegistrationCog")
            if cog is None:
                raise BadStateException("Registration commands are not loaded.")
            citizen = await cog.accept_registration(registration, False)
            await _send_permission_commands(interaction, citizen)

    @discord.ui.button(
        label="Reject",
        emoji="❌",
        style=discord.ButtonStyle.danger,
        custom_id="registration_response_view:reject_citizen",
    )
    async def reject_citizen(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):
        async with respond(interaction) as should_process:
            if not should_process:
                return

            if not await _is_mod(interaction):
                raise BadRequestException("You are not permitted to reject the registration.")

            registration = await _get_registration(interaction)
            cog = interaction.client.get_cog("RegistrationCog")
            if cog is None:
                raise BadStateException("Registration commands are not loaded.")
            await cog.reject_registration(registration)

    @discord.ui.button(
        label="Edit",
        emoji="✏️",
        style=discord.ButtonStyle.secondary,
        custom_id="registration_response_view:edit_citizen",
    )
    async def edit_citizen(self, interaction: discord.Interaction, button: discord.ui.Button):
        async with respond(interaction, defer=False) as should_process:
            if not should_process:
                return

            registration = await _get_registration(interaction)
            if not (registration.poster_id == interaction.user.id or await _is_mod(interaction)):
                raise BadStateException("You are not permitted to edit the registration.")

            await interaction.response.send_modal(await citizen_application_modal(interaction.client.db, registration))


async def _get_registration(interaction: discord.Interaction):
    thread_id = interaction.channel_id
    registration = await interaction.client.db.registrations.fetch_by_thread_id(thread_id)
    if registration is None:
        raise BadStateException("Registration not found")
    return registration


async def _is_mod(interaction: discord.Interaction):
    user = interaction.user
    if not isinstance(user, discord.Member):
        return False

    if user.guild_permissions.administrator:
        return True

    mod_role_id = await interaction.client.db.key_values.get_int(key=CITIZEN_MOD_ROLE_ID_KEY)
    if mod_role_id is None:
        return False
    return any(role.id == mod_role_id for role in user.roles)


async def _send_permission_commands(interaction: discord.Interaction, citizen: Citizen | None) -> None:
    if citizen is None:
        await interaction.edit_original_response(content="Registration was already accepted.")
        return

    msg = await permission_command_embeds(interaction.client, ign=citizen.in_game_name)
    msg["content"] = f"Accepted `{citizen.in_game_name}`. Permission commands:"

    response = await interaction.edit_original_response(**msg)
    if view := msg.get("view"):
        view.message = response

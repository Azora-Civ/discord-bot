import discord

from config import CITIZEN_MOD_ROLE_ID_KEY
from helpers.general import processing_response
from models.ShownException import BadRequestException, BadStateException
from ui.modals.citizen_application_modal import citizen_application_modal


class RegistrationResponseView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Accept",
        style=discord.ButtonStyle.primary,
        custom_id="registration_response_view:accept_citizen",
    )
    async def accept_citizen(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):
        async with processing_response(interaction):
            if not await _is_mod(interaction):
                raise BadRequestException("You are not permitted to accept the registration.")

            registration = await _get_registration(interaction)
            cog = interaction.client.get_cog("RegistrationCog")
            await cog.accept_registration(registration, False)

    @discord.ui.button(
        label="Reject",
        style=discord.ButtonStyle.primary,
        custom_id="registration_response_view:reject_citizen",
    )
    async def reject_citizen(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):
        async with processing_response(interaction):
            if not await _is_mod(interaction):
                raise BadRequestException("You are not permitted to reject the registration.")

            registration = await _get_registration(interaction)
            cog = interaction.client.get_cog("RegistrationCog")
            await cog.reject_registration(registration)

    @discord.ui.button(
        label="Edit",
        style=discord.ButtonStyle.secondary,
        custom_id="registration_response_view:edit_citizen",
    )
    async def edit_citizen(self, interaction: discord.Interaction, button: discord.ui.Button):
        async with processing_response(interaction, show_processing=False):
            registration = await _get_registration(interaction)
            if not (
                registration.poster_id == interaction.user.id
                or await _is_mod(interaction)
            ):
                raise BadStateException("You are not permitted to edit the registration.")

            await interaction.response.send_modal(
                await citizen_application_modal(interaction.client.db, registration)
            )


async def _get_registration(interaction: discord.Interaction):
    thread_id = interaction.channel_id
    registration = await interaction.client.db.registrations.fetch_by_thread_id(thread_id)
    if registration is None:
        raise BadStateException("Registration not found")
    return registration

async def _is_mod(interaction: discord.Interaction):
    user = interaction.user
    if user.guild_permissions.administrator:
        return True

    mod_role_id = await interaction.client.db.key_values.get_int(key=CITIZEN_MOD_ROLE_ID_KEY)
    if mod_role_id is None:
        return False
    return any(role.id == mod_role_id for role in user.roles)


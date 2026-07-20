import discord

from helpers.discord import is_mod
from helpers.general import respond
from models.ShownException import BadStateException
from ui.modals.citizen_application_modal import citizen_application_modal


class RegistrationResponseView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

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
            if not (registration.poster_id == interaction.user.id or await is_mod(interaction)):
                raise BadStateException("You are not permitted to edit the registration.")

            await interaction.response.send_modal(await citizen_application_modal(interaction.client.db, registration))


async def _get_registration(interaction: discord.Interaction):
    thread_id = interaction.channel_id
    registration = await interaction.client.db.registrations.fetch_by_thread_id(thread_id)
    if registration is None:
        raise BadStateException("Registration not found")
    return registration

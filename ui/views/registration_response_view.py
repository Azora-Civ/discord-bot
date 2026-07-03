import discord
from repositories.registrations import RegistrationRepository
from ui.modals.registration_modal import RegistrationModal
from typing import TYPE_CHECKING
from helpers.general import processing_response

if TYPE_CHECKING:
    from services.registration_service import RegistrationService


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
            registration = await _get_registration(interaction)
            service: RegistrationService = interaction.client.get_cog("RegistrationCog").service
            await service.accept_registration(interaction, registration, False)

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
            registration = await _get_registration(interaction)
            service: RegistrationService = interaction.client.get_cog("RegistrationCog").service
            await service.reject_registration(interaction, registration)

    async def on_error(self, interaction, error, item):
        import traceback

        print(f"Error in {item.custom_id}")
        traceback.print_exception(type(error), error, error.__traceback__)


async def _get_registration(interaction: discord.Interaction):
    thread_id = interaction.channel_id
    repo = RegistrationRepository()
    registration = await repo.get_by_thread_id(thread_id)
    return registration

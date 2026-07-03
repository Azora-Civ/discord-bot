import discord
from helpers.general import processing_response
from repositories.registrations import RegistrationRepository
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from services.registration_service import RegistrationService


class RegistrationForceAcceptView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=60)

    @discord.ui.button(label="Accept Anyway...", style=discord.ButtonStyle.red)
    async def force_accept(self, button, interaction):
        async with processing_response(interaction):
            thread_id = interaction.channel_id
            repo = RegistrationRepository()
            registration = await repo.get_by_thread_id(thread_id)

            assert registration is not None, f"Couldn't find registration"

            service: RegistrationService = interaction.client.get_cog("RegistrationCog").service
            await service.accept_registration(interaction, registration, True)

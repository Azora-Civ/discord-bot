from typing import TYPE_CHECKING

import discord

from helpers.general import processing_response
from repositories.registrations import RegistrationRepository

if TYPE_CHECKING:
    from services.registration_service import RegistrationService


class RegistrationForceAcceptView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=60)

    @discord.ui.button(
        label="Accept Anyway...",
        style=discord.ButtonStyle.red,
        custom_id="registration_force_accept_view:accept_anyway",
    )
    async def force_accept(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):
        async with processing_response(interaction):
            thread_id = interaction.channel_id
            repo = RegistrationRepository()
            registration = await repo.fetch_by_thread_id(thread_id)

            assert registration is not None, "Couldn't find registration"

            service: RegistrationService = interaction.client.get_cog("RegistrationCog").service
            await service.accept_registration(registration, True)

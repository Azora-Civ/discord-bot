import discord

from helpers.general import processing_response
from models.registration import Registration
from models.ShownException import BadRequestException
from ui.modals.citizen_application_modal import citizen_application_modal


class RegistrationView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Apply for Citizenship",
        style=discord.ButtonStyle.primary,
        custom_id="registration_view:register_citizen",
    )
    async def register_citizen(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):
        async with processing_response(interaction, show_processing=False):
            citizen = await interaction.client.db.citizens.fetch_by_user_id(interaction.user.id)
            if citizen is not None:
                raise BadRequestException("You are already registered!")

            await interaction.response.send_modal(
                await citizen_application_modal(
                    interaction.client.db,
                    Registration(
                        poster_id=interaction.user.id,
                        is_for_self=True,
                    ),
                )
            )

    @discord.ui.button(
        label="Apply for Someone Else",
        style=discord.ButtonStyle.secondary,
        custom_id="registration_view:register_citizen_other",
    )
    async def register_citizen_other(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):
        async with processing_response(interaction, show_processing=False):
            citizen = await interaction.client.db.citizens.fetch_by_user_id(interaction.user.id)
            if citizen is None:
                raise BadRequestException(
                    "You can only apply for Citizenship for someone else if you are a citizen!"
                )

            await interaction.response.send_modal(
                await citizen_application_modal(
                    interaction.client.db,
                    Registration(
                        poster_id=interaction.user.id,
                        is_for_self=False,
                    ),
                )
            )

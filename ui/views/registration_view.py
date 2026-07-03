import discord

from models.person import Citizenship
from ui.modals.registration_modal import RegistrationModal


class RegistrationView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Register as Citizen",
        style=discord.ButtonStyle.primary,
        custom_id="registration_view:register_citizen",
    )
    async def register_citizen(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):
        try:
            await interaction.response.send_modal(
                RegistrationModal(citizenship=Citizenship.CITIZEN)
            )
        except Exception as e:
            print(type(e), e)
            raise

    @discord.ui.button(
        label="Register as Resident",
        style=discord.ButtonStyle.primary,
        custom_id="registration_view:register_resident",
    )
    async def register_resident(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):
        try:
            await interaction.response.send_modal(
                RegistrationModal(citizenship=Citizenship.RESIDENT)
            )
        except Exception as e:
            print(type(e), e)
            raise

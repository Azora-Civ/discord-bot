import discord

from models.person import Citizenship
from models.registration import Registration
from helpers.general import processing_response
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from services.registration_service import RegistrationService

class RegistrationModal(discord.ui.Modal, title="Citizen/Resident Registration"):
    def __init__(self, citizenship: Citizenship):
        super().__init__()
        self.citizenship = citizenship
        self.title = f"{citizenship} Registration"

    in_game_name = discord.ui.TextInput(
        label="In-game name",
        max_length=32,
    )

    about = discord.ui.TextInput(
        label="What goals/skills do you bring to Azora?",
        style=discord.TextStyle.paragraph,
        max_length=2048,
    )

    follow_rules = discord.ui.TextInput(
        label="Will you follow the server rules?",
        max_length=8,
        placeholder="yes",
    )

    citizenry = discord.ui.TextInput(
        label="Do you understand you'll start at Level 1?",
        max_length=8,
        placeholder="yes",
    )

    async def on_submit(self, interaction: discord.Interaction):
        async with processing_response(interaction):
            registration = Registration(
                user_id=interaction.user.id,
                citizenry=str(self.citizenry.value).strip(),
                about=str(self.about.value).strip(),
                follow_rules=str(self.follow_rules.value).strip(),
                in_game_name=str(self.in_game_name.value).strip(),
                citizenship_type=self.citizenship,
            )
            service: RegistrationService = interaction.client.get_cog("RegistrationCog").service
            await service.request_registration(interaction, registration)
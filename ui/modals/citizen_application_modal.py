from typing import TYPE_CHECKING

import discord
from discord import CheckboxGroupOption, SelectOption

from helpers.general import processing_response
from models.citizen import Citizenship
from models.duchy import Duchy
from models.registration import Registration
from models.ShownException import BadRequestException
from texts import (
    CITIZEN_APPLICATION_MODAL_OTHER,
    CITIZEN_APPLICATION_MODAL_SELF,
    CITIZEN_APPLICATION_MODAL_SUBMITTED,
    CITIZEN_APPLICATION_MODAL_TITLE,
)
from ui.modals.registration_duchy_modal import get_duchies

if TYPE_CHECKING:
    from services.registration_service import RegistrationService


async def citizen_application_modal(registration: Registration):
    duchies = await get_duchies()

    return CitizenApplicationModal(
        duchies=duchies,
        registration=registration,
    )


class CitizenApplicationModal(discord.ui.Modal, title=CITIZEN_APPLICATION_MODAL_TITLE):
    def __init__(
        self,
        duchies: list[Duchy],
        registration: Registration,
    ):
        super().__init__()
        self.registration = registration
        self.duchies = duchies
        texts = CITIZEN_APPLICATION_MODAL_SELF if registration.is_for_self else CITIZEN_APPLICATION_MODAL_OTHER

        self.citizenship_select = discord.ui.Select(
            options=[
                SelectOption(
                    label=citizenship.value,
                    value=citizenship.name,
                    default=registration.citizenship_type == citizenship,
                )
                for citizenship in Citizenship
            ],
        )
        self.citizenship = discord.ui.Label(
            text=texts.citizenship_label,
            component=self.citizenship_select,
        )

        self.in_game_name = discord.ui.TextInput(
            label=texts.username_label,
            default=registration.in_game_name,
            max_length=32,
        )

        self.about = discord.ui.TextInput(
            label=texts.about_label,
            style=discord.TextStyle.paragraph,
            default=registration.data.about,
            max_length=2048,
        )

        self.duchy_select = discord.ui.Select(
            options=[
                SelectOption(
                    label=duchy.name,
                    emoji=duchy.emoji or None,
                    default=duchy.name == registration.data.duchy_name,
                )
                for duchy in duchies
            ],
        )
        self.duchy = discord.ui.Label(
            text=texts.duchy_label,
            component=self.duchy_select,
        )

        self.checks = discord.ui.Label(
            text=texts.ack_label,
            component=discord.ui.CheckboxGroup(
                options=[
                    CheckboxGroupOption(
                        label=texts.ack_law_label,
                        default=registration.id is not None,
                    ),
                    CheckboxGroupOption(
                        label=texts.ack_level_label,
                        default=registration.id is not None,
                    ),
                ],
                min_values=2,
                max_values=2,
            )
        )

        self.add_item(self.citizenship)
        self.add_item(self.in_game_name)
        self.add_item(self.about)
        self.add_item(self.duchy)
        self.add_item(self.checks)

    async def on_submit(self, interaction: discord.Interaction):
        async with processing_response(interaction):
            registration = self.registration

            if len(self.checks.component.values) != 2:
                raise BadRequestException("You must accept both acknowledgements.")

            duchy = {d.name: d for d in self.duchies}[self.duchy_select.values[0]]

            registration.in_game_name = str(self.in_game_name.value).strip()
            registration.citizenship_type = Citizenship[self.citizenship_select.values[0]]
            registration.data.about = str(self.about.value).strip()
            registration.data.duchy_name = duchy.name
            registration.data.duchy_mention = duchy.mention or ""
            registration.data.duchy_emoji = duchy.emoji or ""

            service: RegistrationService = interaction.client.get_cog("RegistrationCog").service
            await service.submit_citizen_application(registration)
            await interaction.edit_original_response(content=CITIZEN_APPLICATION_MODAL_SUBMITTED)

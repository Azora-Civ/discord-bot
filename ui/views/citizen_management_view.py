import discord

from helpers.discord import is_mod
from helpers.general import respond
from models.citizen import Citizen
from ui.modals.citizen_edit_modal import CitizenEditModal


class CitizenManagementView(discord.ui.View):
    def __init__(self, citizen: Citizen):
        super().__init__(timeout=300)
        self.citizen = citizen

    @discord.ui.button(
        label="Edit",
        emoji="✏️",
        style=discord.ButtonStyle.primary,
    )
    async def edit_citizen(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):
        async with respond(interaction, defer=False) as should_process:
            if not should_process:
                return

            if not await is_mod(interaction):
                return

            await interaction.response.send_modal(CitizenEditModal(self.citizen))

    @discord.ui.button(
        label="Remove",
        emoji="🗑️",
        style=discord.ButtonStyle.danger,
    )
    async def remove_citizen(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):
        async with respond(interaction, defer=False) as should_process:
            if not should_process:
                return

            if not await is_mod(interaction):
                return

            await interaction.response.edit_message(
                content=f"Remove citizen `{self.citizen.in_game_name}`?",
                embed=None,
                view=CitizenRemoveConfirmView(self.citizen),
            )


class CitizenRemoveConfirmView(discord.ui.View):
    def __init__(self, citizen: Citizen):
        super().__init__(timeout=300)
        self.citizen = citizen

    @discord.ui.button(
        label="Confirm Remove",
        emoji="🗑️",
        style=discord.ButtonStyle.danger,
    )
    async def confirm(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):
        async with respond(interaction, defer=False) as should_process:
            if not should_process:
                return

            if not await is_mod(interaction):
                return

            service = interaction.client.citizen_service
            await service.remove_citizen(self.citizen.id)
            await interaction.response.edit_message(
                content=f"Removed citizen `{self.citizen.in_game_name}`.",
                embed=None,
                view=None,
            )

    @discord.ui.button(
        label="Cancel",
        emoji="↩️",
        style=discord.ButtonStyle.secondary,
    )
    async def cancel(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):
        async with respond(interaction, defer=False) as should_process:
            if not should_process:
                return

            if not await is_mod(interaction):
                return

            from ui.panels.citizens_panel import citizen_panel

            await interaction.response.edit_message(
                content=None,
                embed=citizen_panel(self.citizen),
                view=CitizenManagementView(self.citizen),
            )

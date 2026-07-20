import discord

from helpers.citizens import citizenship_color
from helpers.general import respond
from models.citizen import Citizen, Citizenship
from models.ShownException import ShownException
from ui.panels.citizens_panel import citizen_panel


class CitizenEditModal(discord.ui.Modal, title="Edit citizen"):
    def __init__(self, citizen: Citizen):
        super().__init__()
        self.citizen = citizen

        self.in_game_name = discord.ui.TextInput(
            label="In-game name",
            default=citizen.in_game_name,
            max_length=32,
            required=True,
        )

        default_users = []
        if citizen.user_id is not None:
            default_users.append(
                discord.SelectDefaultValue(
                    id=citizen.user_id,
                    type=discord.SelectDefaultValueType.user,
                )
            )

        self.discord_user_select = discord.ui.UserSelect(
            placeholder="Select Discord user, or leave empty to unlink",
            min_values=0,
            max_values=1,
            required=False,
            default_values=default_users,
        )
        self.discord_user = discord.ui.Label(
            text="Discord user",
            component=self.discord_user_select,
        )

        self.citizenship_select = discord.ui.Select(
            options=[
                discord.SelectOption(
                    label=citizenship.value,
                    value=citizenship.name,
                    default=citizen.citizenship == citizenship,
                )
                for citizenship in Citizenship
            ],
        )
        self.citizenship = discord.ui.Label(
            text="Citizenship",
            component=self.citizenship_select,
        )

        self.add_item(self.in_game_name)
        self.add_item(self.discord_user)
        self.add_item(self.citizenship)

    async def on_submit(self, interaction: discord.Interaction):
        async with respond(interaction, defer=False) as should_process:
            if not should_process:
                return

            from ui.views.citizen_management_view import CitizenManagementView

            service = interaction.client.citizen_service
            citizen = await service.update_citizen(
                self.citizen,
                in_game_name=str(self.in_game_name.value),
                user_id=_selected_user_id(self.discord_user_select),
                citizenship=Citizenship[self.citizenship_select.values[0]],
            )

            await interaction.response.edit_message(
                embed=citizen_panel(
                    citizen,
                    color=await citizenship_color(interaction.client, citizen.citizenship),
                ),
                view=CitizenManagementView(citizen),
            )

    async def on_error(self, interaction: discord.Interaction, error: Exception):
        if isinstance(error, ShownException):
            await interaction.response.send_message(**error.data, ephemeral=True)
            return

        raise error


def _selected_user_id(select: discord.ui.UserSelect) -> int | None:
    if not select.values:
        return None
    return select.values[0].id

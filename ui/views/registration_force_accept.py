import discord

from helpers.general import respond
from models.ShownException import BadStateException
from ui.views.registration_response_view import _send_permission_commands


class RegistrationForceAcceptView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=60)

    async def on_timeout(self) -> None:
        for item in self.children:
            if isinstance(item, discord.ui.Button):
                item.disabled = True


    @discord.ui.button(
        label="Accept Anyway...",
        emoji="⚠️",
        style=discord.ButtonStyle.red,
        custom_id="registration_force_accept_view:accept_anyway",
    )
    async def force_accept(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):
        async with respond(interaction) as should_process:
            if not should_process:
                return

            self.force_accept.disabled = True

            registration = await interaction.client.db.registrations.fetch_by_thread_id(interaction.channel_id)

            if registration is None:
                raise BadStateException("This registration is no longer pending.")

            cog = interaction.client.get_cog("RegistrationCog")
            if cog is None:
                raise BadStateException("Registration commands are not loaded.")

            citizen = await cog.accept_registration(registration, True)
            await _send_permission_commands(interaction, citizen)

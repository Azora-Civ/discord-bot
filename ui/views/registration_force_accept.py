import discord

from helpers.general import processing_response


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
            registration = await interaction.client.db.registrations.fetch_by_thread_id(
                interaction.channel_id
            )

            assert registration is not None, "Couldn't find registration"

            cog = interaction.client.get_cog("RegistrationCog")
            await cog.accept_registration(registration, True)

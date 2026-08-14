import discord

from helpers.discord import is_mod
from helpers.general import respond
from models.registration import RegistrationStatus
from models.ShownException import BadRequestException, BadStateException


class RegistrationRecruiterView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.select(
        cls=discord.ui.UserSelect,
        placeholder="Select recruiter",
        min_values=1,
        max_values=1,
        custom_id="registration_recruiter_view:select_recruiter",
    )
    async def select_recruiter(
        self,
        interaction: discord.Interaction,
        select: discord.ui.UserSelect,
    ) -> None:
        async with respond(interaction) as should_process:
            if not should_process:
                return

            registration = await interaction.client.db.registrations.fetch_by_thread_id(interaction.channel_id)
            if registration is None:
                raise BadStateException("Registration not found.")

            if registration.status != RegistrationStatus.PENDING:
                raise BadStateException("Recruiter can only be selected for a pending registration.")

            if not (
                registration.poster_id == interaction.user.id
                or await is_mod(interaction)
                or _is_admin(interaction.user)
            ):
                raise BadRequestException("You are not permitted to select the recruiter.")

            user = select.values[0]
            recruiter = await interaction.client.db.citizens.fetch_by_user_id(user.id)
            if recruiter is None:
                raise BadRequestException("Selected user is not a linked citizen.")

            recruiter = await interaction.client.registration_service.select_recruiter(registration, recruiter)
            await interaction.edit_original_response(
                content=(
                    f"Recruiter set to `{recruiter.in_game_name}`. "
                    "It will be counted if this registration is accepted."
                )
            )


async def registration_recruiter_panel(db, registration) -> dict[str, object]:
    if registration.status != RegistrationStatus.PENDING:
        return {"content": "Recruiter selection is closed for this registration.", "view": None}

    current_recruiter = "Not selected"
    if registration.data.recruiter_citizen_id is not None:
        recruiter = await db.citizens.fetch_by_id(registration.data.recruiter_citizen_id)
        current_recruiter = f"`{recruiter.in_game_name}`" if recruiter is not None else "Unknown citizen"

    return {
        "content": (
            "Select which citizen recruited this applicant. "
            "The applicant, mods, and admins can use this dropdown.\n"
            f"Current recruiter: {current_recruiter}"
        ),
        "view": RegistrationRecruiterView(),
    }


def _is_admin(user) -> bool:
    return isinstance(user, discord.Member) and user.guild_permissions.administrator

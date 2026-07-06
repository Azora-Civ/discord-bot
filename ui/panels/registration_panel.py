import discord

from models.registration import Registration, RegistrationStatus
from ui.views.registration_response_view import RegistrationResponseView


def registration_panel(registration: Registration):
    status = str(registration.status).title()
    citizenship = str(registration.citizenship_type).title()

    snitch_hit = "✅" if registration.snitch_hit else "❌"

    embed = discord.Embed(
        title="📋 New Registration Request",
        description=f"Submitted by <@{registration.user_id}>",
        color=discord.Color.gold(),
    )

    embed.add_field(
        name="Applicant",
        value=(
            f"**User:** <@{registration.user_id}>\n"
            f"**In-game name:** {registration.in_game_name}\n"
            f"**Requested status:** {citizenship}"
        ),
        inline=False,
    )

    embed.add_field(
        name="What goals/skills do you bring to Azora?",
        value=registration.about or "No answer provided.",
        inline=False,
    )

    embed.add_field(
        name="Will you follow the server rules?",
        value=registration.follow_rules or "No answer provided.",
        inline=False,
    )

    embed.add_field(
        name="Do you understand you'll start at Level 1?",
        value=registration.citizenry or "No answer provided.",
        inline=False,
    )

    embed.add_field(
        name="Review Info",
        value=(f"**Status:** {status}\n**Hit a snitch:** {snitch_hit}"),
        inline=False,
    )

    response = {"embed": embed}

    if registration.status == RegistrationStatus.PENDING:
        response["view"] = RegistrationResponseView()

    return response
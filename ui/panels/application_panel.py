from urllib.parse import quote_plus

import discord
from discord import Client

import config as cfg
from helpers.discord import get_member
from models.registration import Registration, RegistrationStatus
from texts import CITIZEN_APPLICATION_MODAL_OTHER, CITIZEN_APPLICATION_MODAL_SELF
from ui.views.registration_response_view import RegistrationResponseView


async def registration_panel(bot: Client, db, registration: Registration) -> dict[str, object]:
    status = {
        RegistrationStatus.ACCEPTED: "✅ Approved",
        RegistrationStatus.REJECTED: "❌ Rejected",
        RegistrationStatus.PENDING: "⌛ Pending",
    }[registration.status]
    citizenship = registration.citizenship_type.value

    verified = "✅ Yes" if registration.data.snitch_hit else "❌ No"

    member = await get_member(bot, registration.poster_id)

    texts = CITIZEN_APPLICATION_MODAL_SELF if registration.is_for_self else CITIZEN_APPLICATION_MODAL_OTHER

    if registration.is_for_self:
        applicant = f"**Minecraft Username:** `{registration.in_game_name}`\n**Discord:** <@{registration.poster_id}>"

        if member is not None:
            applicant += (
                f"\n**Discord Account Age:** "
                f"{discord.utils.format_dt(member.created_at, 'D')} "
                f"({discord.utils.format_dt(member.created_at, 'R')})"
            )
    else:
        applicant = (
            f"**Minecraft Username:** `{registration.in_game_name}`\n"
            f"**Submitted by:** <@{registration.poster_id}>\n"
            f"⚠️ This application is for **someone else**."
        )

    embed = discord.Embed(
        title=f"{citizenship} Application",
        color=discord.Color.gold(),
    )

    embed.add_field(
        name="Applicant",
        value=applicant,
        inline=False,
    )

    embed.add_field(
        name=texts.about_label,
        value=registration.data.about or "No answer provided.",
        inline=False,
    )

    duchy = format_duchy(registration)

    embed.add_field(
        name=texts.duchy_label,
        value=duchy or "*No preference provided.*",
        inline=False,
    )

    encoded_ign = quote_plus(registration.in_game_name)

    embed.add_field(
        name="Background",
        value=(
            f"**NameMC:** [View](https://namemc.com/search?q={encoded_ign})\n"
            f"**CivMC Player Tracker:** [View](https://civmc.netlify.app/players/{encoded_ign})"
        ),
        inline=True,
    )

    embed.add_field(
        name="Review",
        value=(f"**Application status:** {status}\n**Snitch verified:** {verified}"),
        inline=True,
    )

    response: dict[str, object] = {
        "embed": embed,
        "view": RegistrationResponseView() if registration.status == RegistrationStatus.PENDING else None,
    }

    if registration.status == RegistrationStatus.PENDING:
        response["content"] = await mentions(db, registration)
    else:
        response["content"] = None

    if registration.data.thread_id is None:
        response["name"] = f"{citizenship} Application - {registration.in_game_name}"

    return response


def format_duchy(registration: Registration) -> str:
    name = registration.data.duchy_name

    if not name:
        return ""

    parts = []

    if registration.data.duchy_emoji:
        parts.append(registration.data.duchy_emoji)

    parts.append(name)

    result = " ".join(parts)

    return result


async def mentions(db, registration: Registration):
    admin_mention = f"<@&{cfg.CITIZEN_MOD_ROLE_ID}>" if cfg.CITIZEN_MOD_ROLE_ID else ""
    return " ".join(
        mention
        for mention in (
            f"<@{registration.poster_id}>",
            admin_mention,
            registration.data.duchy_mention,
        )
        if mention
    )

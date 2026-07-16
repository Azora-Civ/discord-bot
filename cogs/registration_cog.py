import re

import discord
from discord import User, app_commands
from discord.ext import commands

import config as cfg
from helpers.discord_formatting import timestamp
from helpers.general import processing_response
from models.person import Citizenship, Person
from repositories.key_values import KeyValueRepository
from repositories.people import PeopleRepository
from services.registration_service import RegistrationService
from ui.views.registration_response_view import RegistrationResponseView
from ui.views.registration_view import RegistrationView


class RegistrationCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.service = RegistrationService(bot)
        self.snitch_cache = False

    async def _set_snitch_regex(self):
        self.snitch_cache = True

        self.snitch_channel = await KeyValueRepository().get_int(
            key=cfg.REGISTRATION_SNITCH_CHANNEL_ID_KEY
        )

        snitch = await KeyValueRepository().get(key=cfg.REGISTRATION_SNITCH_NAME_KEY)
        snitch_group = await KeyValueRepository().get(key=cfg.REGISTRATION_SNITCH_GROUP_KEY)
        self.snitch_regex = re.compile(
            rf"`\[{re.escape(snitch_group)}\]`\s+\*\*(.+?)\*\*\s+is at {re.escape(snitch)}"
        )

    @app_commands.command(
        name="registration-panel", description="Setup the registration panel here."
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def registration_panel(self, interaction: discord.Interaction):
        async with processing_response(interaction):
            embed = discord.Embed(
                title="Azora Registration",
                description="[ADMIN] Register as a citizen or resident.",
                color=discord.Color.blue(),
            )

            await interaction.channel.send(
                embed=embed,
                view=RegistrationView(),
            )
            await interaction.edit_original_response(content="Registration panel posted.")

    @app_commands.command(
        name="registration-set-channel",
        description="[ADMIN] Setup where registration creates new threads for new registrations.",
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def set_registration_channel(
        self, interaction: discord.Interaction, channel: discord.ForumChannel
    ):
        async with processing_response(interaction, ephemeral=False):
            await KeyValueRepository().set_int(key=cfg.REGISTRATION_FORUM_ID_KEY, value=channel.id)
            await interaction.edit_original_response(
                content=(
                    "Successfully updated the registration channel. Future registrations will now "
                    f"be made under: {channel.mention}"
                )
            )

    @app_commands.command(
        name="registration-set-snitch",
        description="[ADMIN] Setup the snitch to listen for and where to listen.",
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def set_registration_snitch(
        self,
        interaction: discord.Interaction,
        snitch: str,
        snitch_group: str,
        channel: discord.TextChannel,
    ):
        async with processing_response(interaction, ephemeral=False):
            await KeyValueRepository().set(key=cfg.REGISTRATION_SNITCH_NAME_KEY, value=snitch)
            await KeyValueRepository().set(
                key=cfg.REGISTRATION_SNITCH_GROUP_KEY, value=snitch_group
            )
            await KeyValueRepository().set_int(
                key=cfg.REGISTRATION_SNITCH_CHANNEL_ID_KEY, value=channel.id
            )
            await self._set_snitch_regex()
            await interaction.edit_original_response(
                content=(
                    "Successfully updated the registration snitch. Will now listen to snitch hits "
                    f"of '{snitch}' on '{snitch_group}' in {channel.mention}."
                )
            )

    @app_commands.command(
        name="registration-set-roles",
        description="[ADMIN] Setup roles given when registrations are accepted.",
    )
    @app_commands.describe(
        resident_role="Role given to residents. Leave empty to clear.",
        citizen_role="Role given to citizens. Leave empty to clear.",
        member_role="Role given to both residents and citizens. Leave empty to clear.",
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def set_registration_roles(
        self,
        interaction: discord.Interaction,
        resident_role: discord.Role | None = None,
        citizen_role: discord.Role | None = None,
        member_role: discord.Role | None = None,
    ):
        async with processing_response(interaction, ephemeral=False):
            roles = {
                cfg.REGISTRATION_RESIDENT_ROLE_ID_KEY: resident_role,
                cfg.REGISTRATION_CITIZEN_ROLE_ID_KEY: citizen_role,
                cfg.REGISTRATION_MEMBER_ROLE_ID_KEY: member_role,
            }

            repo = KeyValueRepository()
            for key, role in roles.items():
                if role is None:
                    await repo.delete(key)
                    continue

                await repo.set_int(key=key, value=role.id)

            await interaction.edit_original_response(
                content=(
                    "Successfully updated registration roles.\n"
                    f"Resident: {resident_role.mention if resident_role else 'None'}\n"
                    f"Citizen: {citizen_role.mention if citizen_role else 'None'}\n"
                    f"Resident/Citizen: {member_role.mention if member_role else 'None'}"
                )
            )

    @app_commands.command(
        name="citizenship",
        description="Show information about yourself or another citizen/resident.",
    )
    async def citizenship(
        self,
        interaction: discord.Interaction,
        user: discord.User | None,
    ):
        async with processing_response(interaction, ephemeral=False):
            user: User = user or interaction.user
            p_repo = PeopleRepository()
            person = await p_repo.get_by_user_id(user.id)

            embed = get_person_embed(user, person)

            await interaction.edit_original_response(content=None, embed=embed)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if not self.snitch_cache:
            await self._set_snitch_regex()

        if self.snitch_channel != message.channel.id:
            return

        match = self.snitch_regex.search(message.content)
        if match:
            ign = match.group(1)
            await self.service.hit_registration_snitch(self.bot, ign)


def get_person_embed(user: discord.User | discord.Member, person: Person | None) -> discord.Embed:
    if person is None:
        embed = discord.Embed(
            title="Person Lookup",
            description=f"{user.mention} is not registered as a citizen or resident.",
            color=discord.Color.red(),
        )
        embed.add_field(name="User", value=user.mention, inline=False)
        embed.add_field(name="Citizenship", value="Not registered", inline=True)
        return embed

    embed = discord.Embed(
        title="Person Lookup",
        description=f"Information for {user.mention}",
        color=discord.Color.green()
        if person.citizenship == Citizenship.CITIZEN
        else discord.Color.blue(),
    )

    embed.add_field(name="User", value=user.mention, inline=False)
    embed.add_field(name="In-game name", value=person.in_game_name, inline=True)
    embed.add_field(name="Citizenship", value=str(person.citizenship), inline=True)

    embed.add_field(
        name="Joined",
        value=timestamp(person.created_at),
        inline=False,
    )

    return embed


async def setup(bot: commands.Bot):
    await bot.add_cog(RegistrationCog(bot), guild=cfg.GUILD)
    bot.add_view(RegistrationView())
    bot.add_view(RegistrationResponseView())

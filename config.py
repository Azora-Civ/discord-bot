import os
from pathlib import Path

import discord
from dotenv import load_dotenv

load_dotenv()


def _required_env(name: str) -> str:
    value = os.getenv(name)
    if value is None or not value.strip():
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def _env_int(name: str, default: int | None = None, *, minimum: int | None = None) -> int:
    raw_value = os.getenv(name)
    if raw_value is None or not raw_value.strip():
        if default is None:
            raise RuntimeError(f"Missing required environment variable: {name}")
        value = default
    else:
        try:
            value = int(raw_value)
        except ValueError as exc:
            raise RuntimeError(f"Environment variable {name} must be an integer.") from exc

    if minimum is not None and value < minimum:
        raise RuntimeError(f"Environment variable {name} must be at least {minimum}.")

    return value


def _env_optional_int(name: str, *, minimum: int | None = None) -> int | None:
    raw_value = os.getenv(name)
    if raw_value is None or not raw_value.strip():
        return None

    try:
        value = int(raw_value)
    except ValueError as exc:
        raise RuntimeError(f"Environment variable {name} must be an integer.") from exc

    if minimum is not None and value < minimum:
        raise RuntimeError(f"Environment variable {name} must be at least {minimum}.")

    return value


# General
TOKEN = _required_env("DISCORD_TOKEN")
GUILD_ID = _env_int("GUILD_ID")
GUILD = discord.Object(id=GUILD_ID)
KIRA_USER_ID = _env_int("KIRA_USER_ID", 952325487663939645)


# DB
DB_PATH = os.getenv("DB_PATH") or "azora.db"


# Logging
LOG_FILE = os.getenv("LOG_FILE") or "bot.log"
LOG_PATH = Path(os.getenv("LOG_PATH") or "logs")


# Citizen
CITIZEN_MOD_ROLE_ID = _env_optional_int("CITIZEN_MOD_ROLE_ID")

# Registration
REGISTRATION_EMBED_KEY = "registration.embed"
REGISTRATION_DUCHY_KEY = "registration.duchy"
REGISTRATION_FORUM_ID = _env_optional_int("REGISTRATION_FORUM_ID")
REGISTRATION_ACCEPTED_TAG_ID = _env_optional_int("REGISTRATION_ACCEPTED_TAG_ID")
REGISTRATION_PENDING_TAG_ID = _env_optional_int("REGISTRATION_PENDING_TAG_ID")
REGISTRATION_REJECTED_TAG_ID = _env_optional_int("REGISTRATION_REJECTED_TAG_ID")
REGISTRATION_PRIMARY_TAG_ID = _env_optional_int("REGISTRATION_PRIMARY_TAG_ID")
REGISTRATION_SECONDARY_TAG_ID = _env_optional_int("REGISTRATION_SECONDARY_TAG_ID")
REGISTRATION_RESIDENCY_TAG_ID = _env_optional_int("REGISTRATION_RESIDENCY_TAG_ID")

REGISTRATION_SNITCH_CHANNEL_ID_KEY = "registration.snitch_channel_id"
REGISTRATION_SNITCH_NAME_KEY = "registration.snitch_name"
REGISTRATION_SNITCH_GROUP_KEY = "registration.snitch_group"

REGISTRATION_RESIDENT_ROLE_ID = _env_optional_int("REGISTRATION_RESIDENT_ROLE_ID")
REGISTRATION_CITIZEN_ROLE_ID = _env_optional_int("REGISTRATION_CITIZEN_ROLE_ID")
REGISTRATION_PRIMARY_CITIZEN_ROLE_ID = _env_optional_int("REGISTRATION_PRIMARY_CITIZEN_ROLE_ID")
REGISTRATION_SECONDARY_CITIZEN_ROLE_ID = _env_optional_int("REGISTRATION_SECONDARY_CITIZEN_ROLE_ID")
REGISTRATION_MEMBER_ROLE_ID = _env_optional_int("REGISTRATION_MEMBER_ROLE_ID")

# Farms
FARMS_MOD_ROLE_ID_KEY = "farms.mod_role_id"
FARMS_PANEL_CHANNEL_ID_KEY = "farms.panel_channel_id"
FARMS_PANEL_MESSAGE_ID_KEY = "farms.panel_message_id"

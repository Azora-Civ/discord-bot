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


# General
TOKEN = _required_env("DISCORD_TOKEN")
GUILD_ID = _env_int("GUILD_ID")
GUILD = discord.Object(id=GUILD_ID)
KIRA_USER_ID = _env_int("KIRA_USER_ID", 952325487663939645)


# DB
DB_PATH = os.getenv("DB_PATH") or "azora.db"
DB_BACKUP_DIR = Path(os.getenv("DB_BACKUP_DIR") or "backups")
DB_MAX_BACKUPS = _env_int("DB_MAX_BACKUPS", 10, minimum=0)


# Logging
LOG_FILE = os.getenv("LOG_FILE") or "bot.log"
LOG_PATH = Path(os.getenv("LOG_PATH") or "logs")


# Citizen
CITIZEN_MOD_ROLE_ID_KEY = "citizen.mod_role_id"
CITIZEN_SNITCH_CHANNEL_ID_KEY = "citizen.snitch_channel_id"

# Registration
REGISTRATION_EMBED_KEY = "registration.embed"
REGISTRATION_DUCHY_KEY = "registration.duchy"
REGISTRATION_FORUM_ID_KEY = "registration.forum_id"

REGISTRATION_SNITCH_CHANNEL_ID_KEY = "registration.snitch_channel_id"
REGISTRATION_SNITCH_NAME_KEY = "registration.snitch_name"
REGISTRATION_SNITCH_GROUP_KEY = "registration.snitch_group"

REGISTRATION_RESIDENT_ROLE_ID_KEY = "registration.resident_role_id"
REGISTRATION_CITIZEN_ROLE_ID_KEY = "registration.citizen_role_id"
REGISTRATION_MEMBER_ROLE_ID_KEY = "registration.member_role_id"

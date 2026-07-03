import os
import discord
from dotenv import load_dotenv
from pathlib import Path

load_dotenv()

# General
TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = os.getenv("GUILD_ID")
GUILD = discord.Object(id=GUILD_ID)
DB_PATH = os.getenv("DB_PATH") or "azora.db"
DB_BACKUP_DIR = Path(os.getenv("DB_BACKUP_DIR") or "backups")
DB_MAX_BACKUPS = os.getenv("DB_MAX_BACKUPS") or 10
LOG_FILE = os.getenv("LOG_FILE") or "bot.log"
LOG_PATH = Path(os.getenv("LOG_PATH") or "logs")

# Registration
REGISTRATION_ADMIN_ROLE_ID_KEY = "registration.admin_role_id"
REGISTRATION_FORUM_ID_KEY = "registration.forum_id"
REGISTRATION_SNITCH_CHANNEL_ID_KEY = "registration.snitch_channel_id"
REGISTRATION_SNITCH_NAME_KEY = "registration.snitch_name"
REGISTRATION_SNITCH_GROUP_KEY = "registration.snitch_group"

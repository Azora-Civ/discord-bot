import json

from models.embed_config import EmbedConfig
from repositories.key_values import KeyValueRepository
from ui.views.registration_view import RegistrationView
import config as cfg

async def get_embed_config():
    embed_config_json = await KeyValueRepository().get(key=cfg.REGISTRATION_EMBED_KEY)

    if embed_config_json:
        embed_config = EmbedConfig(**json.loads(embed_config_json))
    else:
        embed_config = EmbedConfig(
            title="Azora Registration",
            description="Register as a citizen or resident.",
            colour=0x3498DB
        )
    return embed_config

async def registration_panel():
    embed_config = await get_embed_config()
    embed = embed_config.create_embed()

    return {
        "embed": embed,
        "view": RegistrationView()
    }

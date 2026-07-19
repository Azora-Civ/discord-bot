import json

import config as cfg
from models.embed_config import EmbedConfig
from ui.views.registration_view import RegistrationView


async def get_embed_config(db):
    embed_config_json = await db.key_values.get(key=cfg.REGISTRATION_EMBED_KEY)

    if embed_config_json:
        embed_config = EmbedConfig(**json.loads(embed_config_json))
    else:
        embed_config = EmbedConfig(
            title="Azora Registration",
            description="Register as a citizen or resident.",
            colour=0x3498DB
        )
    return embed_config

async def registration_panel(db):
    embed_config = await get_embed_config(db)
    embed = embed_config.create_embed()

    return {
        "embed": embed,
        "view": RegistrationView()
    }

from dataclasses import dataclass
from models.permission import PermissionLevel


@dataclass
class GroupPermission:
    role_id: int
    namelayer: str
    level: PermissionLevel

    id: int | None = None

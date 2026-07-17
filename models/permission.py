from enum import Enum
from attr import dataclass


class PermissionLevel(Enum):
    DEFAULT = 0
    MEMBERS = 1
    MODS = 2
    ADMINS = 3
    OWNER = 4
    PRIMARY_OWNER = 5


@dataclass
class Permission:
    ign: str
    namelayer: str
    level: PermissionLevel

    id: int | None = None
    source: str | None = None

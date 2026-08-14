from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum


class Citizenship(StrEnum):
    PRIMARY_CITIZEN = "Primary Citizen"
    SECONDARY_CITIZEN = "Secondary Citizen"
    RESIDENT = "Resident"


@dataclass
class CitizenData:
    recruitments: int = 0


@dataclass
class Citizen:
    in_game_name: str
    user_id: int | None
    citizenship: Citizenship
    data: CitizenData = field(default_factory=CitizenData)
    joined_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    last_online: datetime = field(default_factory=lambda: datetime.now(UTC))
    id: int | None = None

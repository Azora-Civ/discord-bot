from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum


class Citizenship(StrEnum):
    CITIZEN = "Citizen"
    RESIDENT = "Resident"


@dataclass
class Citizen:
    in_game_name: str
    user_id: int | None
    citizenship: Citizenship
    joined_at: datetime = datetime.now(UTC)
    last_online: datetime = datetime.now(UTC)
    id: int | None = None

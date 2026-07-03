from dataclasses import dataclass
from enum import StrEnum

class Citizenship(StrEnum):
    CITIZEN = "Citizen"
    RESIDENT = "Resident"
    PENDING = "Pending"

@dataclass(slots=True, kw_only=True)
class Person:
    user_id: int
    in_game_name: str
    citizenship: Citizenship
    created_at: str | None = None

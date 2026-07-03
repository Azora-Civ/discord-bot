from dataclasses import dataclass
from enum import StrEnum
from typing import Optional

from models.person import Citizenship


class RegistrationStatus(StrEnum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"


@dataclass(slots=True, kw_only=True)
class Registration:
    user_id: int
    citizenship_type: Citizenship
    in_game_name: str
    about: str
    follow_rules: str
    citizenry: str

    id: Optional[int] = None
    thread_id: int | None = None
    message_id: int | None = None
    snitch_hit: bool = False
    status: RegistrationStatus = RegistrationStatus.PENDING
    created_at: Optional[str] = None

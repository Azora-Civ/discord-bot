from dataclasses import dataclass, field
from enum import StrEnum

from models.citizen import Citizenship


class RegistrationStatus(StrEnum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"


@dataclass
class RegistrationData:
    about: str = ""

    snitch_hit: bool = False

    thread_id: int | None = None
    message_id: int | None = None

    duchy_name: str = ""
    duchy_mention: str = ""
    duchy_emoji: str = ""


@dataclass
class Registration:
    poster_id: int
    is_for_self: bool
    citizenship_type: Citizenship = Citizenship.PRIMARY_CITIZEN
    in_game_name: str = ""
    data: RegistrationData = field(default_factory=RegistrationData)

    id: int | None = None
    status: RegistrationStatus = RegistrationStatus.PENDING

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class FarmState(StrEnum):
    UNKNOWN = "unknown"
    GROWING = "growing"
    BEING_FARMED = "being_farmed"
    FULLY_GROWN = "fully grown"

@dataclass
class Farm:
    name: str
    posxyz: str
    regrow_time: int
    farm_time: int
    started_time: int | None = None
    finished_time: int | None = None
    additional_data: dict[str, Any] = field(default_factory=dict)

    id: int | None = None

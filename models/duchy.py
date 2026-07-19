from dataclasses import dataclass


@dataclass
class Duchy:
    name: str
    mention: str | None
    emoji: str | None

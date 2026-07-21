from dataclasses import dataclass


@dataclass
class RoleTrack:
    name: str
    role_ids: list[int]

    id: int | None = None

from dataclasses import dataclass


@dataclass(slots=True, kw_only=True)
class KeyValue:
    key: str
    value: str

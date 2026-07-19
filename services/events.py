import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import Generic, TypeVar

from models.citizen import Citizen
from models.permission import Permission
from models.permission_group import GroupPermission
from models.registration import Registration

log = logging.getLogger(__name__)

T = TypeVar("T")
EventHandler = Callable[[T], Awaitable[None]]


class EventHook(Generic[T]):
    def __init__(self, name: str):
        self.name = name
        self._handlers: list[EventHandler[T]] = []

    def subscribe(self, handler: EventHandler[T]) -> EventHandler[T]:
        self._handlers.append(handler)
        return handler

    def unsubscribe(self, handler: EventHandler[T]) -> None:
        self._handlers.remove(handler)

    async def emit(self, event: T) -> None:
        for handler in tuple(self._handlers):
            try:
                await handler(event)
            except Exception:
                log.exception("Event handler failed: %s -> %s", self.name, handler)


class ChangeKind(StrEnum):
    CREATED = "created"
    UPDATED = "updated"
    DELETED = "deleted"


class CitizenChangeKind(StrEnum):
    CREATED = "created"
    UPDATED = "updated"
    DELETED = "deleted"
    ACTIVITY = "activity"


@dataclass(frozen=True)
class CitizenChangedEvent:
    kind: CitizenChangeKind
    citizen: Citizen
    previous: Citizen | None = None
    source: str | None = None


@dataclass(frozen=True)
class RegistrationChangedEvent:
    kind: ChangeKind
    registration: Registration
    previous: Registration | None = None
    source: str | None = None


@dataclass(frozen=True)
class PermissionChangedEvent:
    kind: ChangeKind
    permission: Permission
    previous: Permission | None = None
    source: str | None = None


@dataclass(frozen=True)
class GroupPermissionChangedEvent:
    kind: ChangeKind
    permission: GroupPermission
    previous: GroupPermission | None = None
    source: str | None = None

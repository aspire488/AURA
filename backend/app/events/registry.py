from __future__ import annotations

from app.events.bus import Subscriber
from app.events.event import EventType


class EventRegistry:
    """Simple subscriber registration. ponytail: no decorators, no auto-discovery."""

    def __init__(self):
        self._entries: list[tuple[EventType, Subscriber]] = []

    def register(self, event_type: EventType, handler: Subscriber) -> None:
        self._entries.append((event_type, handler))

    def get_all(self) -> list[tuple[EventType, Subscriber]]:
        return list(self._entries)


registry = EventRegistry()

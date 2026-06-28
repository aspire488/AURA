"""Subscriber that forwards strategic events to the Strategic Intelligence manager."""

from __future__ import annotations

from app.events.event import BaseEvent
from app.strategic_intelligence.manager import process_event

class StrategicIntelligenceSubscriber:
    async def __call__(self, event: BaseEvent) -> None:
        await process_event(event)

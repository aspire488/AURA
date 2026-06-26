from __future__ import annotations

import logging

from app.events.event import BaseEvent

logger = logging.getLogger(__name__)


class ObservationSubscriber:
    async def __call__(self, event: BaseEvent) -> None:
        logger.info("[observation] %s: %s", event.event_type, event.source)


class MemorySubscriber:
    async def __call__(self, event: BaseEvent) -> None:
        logger.info("[memory] %s: %s", event.event_type, event.payload)


class MetricsSubscriber:
    async def __call__(self, event: BaseEvent) -> None:
        from app.intelligence.metrics import metrics
        metrics.record_event(event.event_type.value)


# ponytail: thin adapter — when Observation System lands, it becomes the
# single event subscriber and calls IdentityResolver directly.
class IdentitySubscriber:
    async def __call__(self, event: BaseEvent) -> None:
        from app.identity.resolver import resolve_identity
        await resolve_identity(event)

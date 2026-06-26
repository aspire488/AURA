from __future__ import annotations

import logging

from app.events.event import BaseEvent

logger = logging.getLogger(__name__)


# ponytail: thin adapter — calls observe() which handles normalize + identity + persist.
class ObservationSubscriber:
    async def __call__(self, event: BaseEvent) -> None:
        from app.observation.observer import observe
        await observe(event)


class MetricsSubscriber:
    async def __call__(self, event: BaseEvent) -> None:
        from app.intelligence.metrics import metrics
        metrics.record_event(event.event_type.value)

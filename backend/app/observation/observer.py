from __future__ import annotations

import logging
import time

from app.events.event import BaseEvent
from app.observation.normalizer import normalize
from app.observation.store import observation_store

logger = logging.getLogger(__name__)


async def observe(event: BaseEvent) -> None:
    """Transform event into observation, resolve identity, persist. No reasoning."""
    from app.identity.resolver import resolve_identity
    from app.intelligence.metrics import metrics

    start = time.perf_counter()
    try:
        identity = await resolve_identity(event)
        obs = normalize(event, identity.identity_id)
        await observation_store.append(obs)
        metrics.record_observation_created(round((time.perf_counter() - start) * 1000, 2))
    except Exception:
        logger.exception("Observation failed for event %s", event.event_id)
        metrics.record_observation_failed()

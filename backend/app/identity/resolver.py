from __future__ import annotations

import logging

from app.events.event import BaseEvent
from app.identity.identity import Identity
from app.identity.manager import get_identity_manager

logger = logging.getLogger(__name__)


async def resolve_identity(event: BaseEvent) -> Identity:
    """Resolve identity from event. ponytail: session_id as identity key, create if unknown.

    Returns the resolved Identity. Attaches identity_id to event metadata for downstream.
    All event parsing/normalization lives here; subscriber is a thin adapter.
    """
    from app.intelligence.metrics import metrics
    try:
        return await _resolve(event)
    except Exception:
        logger.exception("Identity resolution failed for %s", event.event_id)
        metrics.record_subscriber_failure()
        raise


async def _resolve(event: BaseEvent) -> Identity:
    from app.intelligence.metrics import metrics
    manager = get_identity_manager()

    # Use session_id as primary identity key — each session = one cognitive identity
    name = event.session_id or event.actor or "anonymous"

    # Check existing
    existing = await manager.find_identity(name=name)
    if existing:
        await manager.touch_identity(existing[0].identity_id)
        _attach(event, existing[0])
        metrics.record_identity_resolution()
        return existing[0]

    # Create placeholder
    identity = await manager.create_identity(
        display_name=name,
        metadata={"source_event_id": event.event_id, "event_type": event.event_type.value},
    )
    _attach(event, identity)
    metrics.record_identity_resolution()
    logger.debug("Created placeholder identity %s for %s", identity.identity_id, name)
    return identity


def _attach(event: BaseEvent, identity: Identity) -> None:
    """Attach resolved identity to event metadata. ponytail: mutate in-place."""
    event.metadata.correlation_id = identity.identity_id

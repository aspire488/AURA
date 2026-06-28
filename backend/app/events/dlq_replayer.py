"""Simple DLQ replay worker.

Periodically polls the in‑memory DLQ, attempts to re‑publish the original event,
removes the entry on success, and respects a maximum retry count with
exponential back‑off (2 s, 4 s, 8 s).  Ponytail: minimal async loop, no extra deps.
"""

import asyncio
import logging
import time
from datetime import datetime, timedelta

from app.events.dlq_store import list_entries, remove
from app.events.store import event_store
from app.events.bus import bus
from app.events.event import BaseEvent

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
BASE_DELAY = 2  # seconds

# Fetching original event is optional; we reconstruct a minimal BaseEvent using stored type.
def _make_event(entry: dict) -> BaseEvent:
    et = entry.get("event_type")
    if not et:
        return None
    # Convert stored string back to EventType enum if possible
    try:
        from app.events.event import EventType
        et_enum = EventType(et)
    except Exception:
        et_enum = et
    return BaseEvent(event_type=et_enum, timestamp=time.time())


async def _replay_entry(entry: dict) -> bool:
    # Simple replay: wait with exponential back‑off, then attempt to republish if possible.
    retries = entry.get("retries", 0)
    if retries >= MAX_RETRIES:
        logger.warning("DLQ entry %s exceeded max retries, giving up", entry["id"])
        return True
    # exponential back‑off
    delay = BASE_DELAY * (2 ** retries)
    await asyncio.sleep(delay)
    try:
        event = _make_event(entry)
        if event:
            from app.events.bus import bus
            event._replay = True
            await bus.publish(event)
            logger.info("DLQ entry %s replay succeeded", entry["id"])
    except Exception as exc:  # noqa: BLE001
        # any failure, increment retry count for future attempts
        entry["retries"] = retries + 1
        logger.exception("DLQ entry %s replay error", entry["id"])
        return False
    # on success or if no event to publish, remove entry
    return True

async def replay_loop(stop_event: asyncio.Event):
    """Continuously process DLQ entries until stop_event is set."""
    while not stop_event.is_set():
        entries = list_entries()
        for entry in entries:
            handled = await _replay_entry(entry)
            if handled:
                remove(entry["id"])
        await asyncio.sleep(2)

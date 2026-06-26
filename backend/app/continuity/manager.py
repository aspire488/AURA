"""Continuity manager – fetch and update persisted session state.

Provides deterministic CRUD; callers can store arbitrary JSON state.
"""

from __future__ import annotations

import time

from app.continuity.model import Continuity
from app.continuity.store import continuity_store


async def get_or_create(session_id: str) -> Continuity:
    """Return existing continuity for *session_id* or create a new one.
    ponytail: deterministic – first match wins.
    """
    existing = await continuity_store.find_by_session(session_id)
    if existing:
        return existing
    continuity = Continuity(session_id=session_id, state={})
    await continuity_store.save(continuity)
    return continuity


async def update_state(continuity_id: str, new_state: dict) -> Continuity | None:
    cont = await continuity_store.get(continuity_id)
    if not cont:
        return None
    cont.state = new_state
    cont.updated_at = time.time()
    await continuity_store.save(cont)
    return cont

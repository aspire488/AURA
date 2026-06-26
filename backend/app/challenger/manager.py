from __future__ import annotations

import logging
import time

from app.challenger.challenger import Challenge
from app.challenger.store import challenge_store
from app.reasoning.manager import get as get_reasoning
from app.belief.manager import get as get_belief
from app.opinion.manager import get as get_opinion

logger = logging.getLogger(__name__)


async def create(typ: str, target_ids: list[str], description: str = "", **kwargs) -> Challenge:
    """Create a challenge record, dedup by type+exact target set."""
    existing = await challenge_store.find_by_type_and_targets(typ, target_ids)
    if existing:
        return existing
    ch = Challenge(
        type=typ,
        target_ids=sorted(set(target_ids)),
        description=description,
        metadata=kwargs.get("metadata", {}),
    )
    await challenge_store.save(ch)
    # Refresh any decisions impacted by this challenge – minimal hook
    from app.oracle.manager import on_challenge_updated
    await on_challenge_updated(ch.challenge_id)
    return ch


async def get(challenge_id: str) -> Challenge | None:
    return await challenge_store.get(challenge_id)


async def list_all(state: str = "", limit: int = 100) -> list[Challenge]:
    return await challenge_store.list_all(state, limit)


async def invalidate(challenge_id: str) -> Challenge | None:
    return await challenge_store.invalidate(challenge_id)


async def merge_duplicates() -> None:
    """Placeholder: find exact duplicates and invalidate extras. ponytail: no-op for now."""
    # Could scan all challenges, but skip for minimal implementation
    pass


# Simple detection stubs ----------------------------------------------------

async def _detect_conflicting_beliefs(belief_ids: list[str]) -> list[Challenge]:
    # Very naive: if any two statements contain opposite words "yes"/"no"
    # For now, return empty list (no detection).
    return []


async def _detect_contradictory_opinions(opinion_ids: list[str]) -> list[Challenge]:
    return []


async def _detect_unsupported_reasoning(reasoning_id: str) -> list[Challenge]:
    return []


async def evaluate(reasoning_id: str) -> None:
    """Run all detection checks for a reasoning record and create challenges as needed."""
    reasoning = await get_reasoning(reasoning_id)
    if not reasoning:
        return
    # Detect conflicting beliefs
    for ch in await _detect_conflicting_beliefs(reasoning.belief_ids):
        await challenge_store.save(ch)
    # Detect contradictory opinions
    for ch in await _detect_contradictory_opinions(reasoning.opinion_ids):
        await challenge_store.save(ch)
    # Detect unsupported reasoning
    for ch in await _detect_unsupported_reasoning(reasoning_id):
        await challenge_store.save(ch)

# Hook integration ----------------------------------------------------------

async def on_reasoning_updated(reasoning_id: str) -> None:
    """Called when a reasoning record changes. ponytail: trigger evaluation."""
    await evaluate(reasoning_id)

"""Oracle manager – deterministic decision engine.

Implements CRUD and derives a final decision from linked reasoning and challenges.
"""

from __future__ import annotations

import logging
import time
from typing import List

from app.oracle.oracle import Decision
from app.oracle.store import decision_store
from app.reasoning.manager import get as get_reasoning


logger = logging.getLogger(__name__)

# CRUD ---------------------------------------------------------------------

async def create(reasoning_ids: List[str] | None = None, challenger_ids: List[str] | None = None, **kwargs) -> Decision:
    """Create a decision linking reasonings and challenges.
    ponytail: dedup by exact reasoning+challenger set.
    """
    reasoning_ids = sorted(set(reasoning_ids or []))
    challenger_ids = sorted(set(challenger_ids or []))
    # simple dedup check
    # ponytail: dedup by exact reasoning+challenger set – skipped for simplicity
    decision = Decision(
        reasoning_ids=reasoning_ids,
        challenger_ids=challenger_ids,
        metadata=kwargs.get("metadata", {}),
    )
    await decision_store.save(decision)
    return decision

async def get(decision_id: str) -> Decision | None:
    return await decision_store.get(decision_id)

async def list_all(state: str = "", limit: int = 100) -> List[Decision]:
    return await decision_store.list_all(state, limit)

async def update(decision: Decision) -> None:
    """Persist mutated decision. Caller updates fields; we refresh timestamp."""
    decision.updated_at = time.time()
    await decision_store.save(decision)

async def invalidate(decision_id: str) -> Decision | None:
    return await decision_store.invalidate(decision_id)

async def merge(decision_id: str, other_id: str) -> Decision | None:
    """Merge two decisions; keep first, union IDs, concatenate conclusions."""
    keep = await decision_store.get(decision_id)
    drop = await decision_store.get(other_id)
    if not keep or not drop:
        return None
    # union lists
    keep.reasoning_ids = sorted(set(keep.reasoning_ids + drop.reasoning_ids))
    keep.challenger_ids = sorted(set(keep.challenger_ids + drop.challenger_ids))
    # combine conclusions (simple)
    if drop.final_conclusion and drop.final_conclusion not in keep.final_conclusion:
        keep.final_conclusion = (keep.final_conclusion + " | " + drop.final_conclusion).strip(" | ")
    keep.updated_at = time.time()
    await decision_store.save(keep)
    await invalidate(other_id)
    return keep

# Derivation ---------------------------------------------------------------

async def derive_final(decision_id: str) -> Decision | None:
    """Derive deterministic final conclusion from linked reasonings and challenges.
    ponytail: simple concatenation of reasoning conclusions; challenges are noted.
    """
    decision = await decision_store.get(decision_id)
    if not decision:
        return None
    conclusions: List[str] = []
    for rid in decision.reasoning_ids:
        r = await get_reasoning(rid)
        if r and getattr(r, "conclusion", None):
            conclusions.append(r.conclusion)
    # record any challenged reasonings (placeholder)
    # For now, just note count of challenges
    challenge_notes = f"Challenges: {len(decision.challenger_ids)}"
    final = " | ".join(conclusions + [challenge_notes]) if conclusions else challenge_notes
    decision.final_conclusion = final
    decision.status = "finalized"
    decision.updated_at = time.time()
    await decision_store.save(decision)
    return decision

# Hook from challenger -----------------------------------------------------

async def on_challenge_updated(challenge_id: str) -> None:
    """Refresh any decisions that reference this challenge."""
    decisions = await decision_store.find_by_challenger(challenge_id)
    for d in decisions:
        await derive_final(d.decision_id)

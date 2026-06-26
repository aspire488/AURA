from __future__ import annotations

import logging
import time

from app.opinion.opinion import Opinion
from app.opinion.store import opinion_store
from app.confidence.store import confidence_store

logger = logging.getLogger(__name__)


async def create(belief_ids: list[str], **kwargs) -> Opinion:
    """Create opinion for a set of beliefs. ponytail: dedup by exact belief set."""
    # dedup by exact set (order‑insensitive)
    existing = await opinion_store.find_by_exact_beliefs(belief_ids)
    if existing:
        return existing
    opinion = Opinion(
        belief_ids=sorted(set(belief_ids)),
        metadata=kwargs.get("metadata", {}),
    )
    # initial compute
    await recompute(opinion.opinion_id)
    await opinion_store.save(opinion)
    return opinion


async def update(opinion: Opinion) -> None:
    """Persist mutated opinion. ponytail: caller mutates fields, we update timestamp."""
    opinion.updated_at = time.time()
    await opinion_store.save(opinion)


async def get(opinion_id: str) -> Opinion | None:
    return await opinion_store.get(opinion_id)


async def list_all(state: str = "", limit: int = 100) -> list[Opinion]:
    return await opinion_store.list_all(state, limit)


async def merge(opinion_id: str, other_id: str) -> Opinion | None:
    """Merge two opinions, keep first, union belief refs, keep higher value."""
    keep = await opinion_store.get(opinion_id)
    drop = await opinion_store.get(other_id)
    if not keep or not drop:
        return None
    # union belief ids
    keep.belief_ids = sorted(set(keep.belief_ids) | set(drop.belief_ids))
    # keep higher value
    keep.value = max(keep.value, drop.value)
    await update(keep)
    await invalidate(other_id)
    return keep


async def invalidate(opinion_id: str) -> Opinion | None:
    """Mark opinion inactive."""
    opinion = await opinion_store.get(opinion_id)
    if not opinion:
        return None
    opinion.state = "inactive"
    await update(opinion)
    return opinion


async def recompute(opinion_id: str) -> Opinion | None:
    """Recompute opinion value from referenced beliefs' confidences. ponytail: simple average."""
    opinion = await opinion_store.get(opinion_id)
    if not opinion:
        return None
    if opinion.state != "active":
        opinion.value = 0.0
        await update(opinion)
        return opinion
    total = 0.0
    count = 0
    for bid in opinion.belief_ids:
        conf = await confidence_store.find_by_belief(bid)
        if conf:
            total += conf.value
            count += 1
    opinion.value = (total / count) if count else 0.0
    await update(opinion)
    return opinion


async def on_belief_updated(belief_id: str) -> None:
    """Hook: recompute any opinion that references this belief."""
    opinions = await opinion_store.find_by_belief(belief_id)
    for op in opinions:
        await recompute(op.opinion_id)

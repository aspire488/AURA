from __future__ import annotations

import logging
import time

from app.belief.belief import Belief
from app.belief.store import belief_store

logger = logging.getLogger(__name__)


async def create(statement: str, entity_ids: list[str] | None = None, **kwargs) -> Belief:
    """Create a belief. ponytail: dedup by exact statement."""
    from app.intelligence.metrics import metrics

    existing = await belief_store.find_by_statement(statement)
    if existing:
        metrics.record_belief_updated()
        return existing

    belief = Belief(
        statement=statement,
        entity_ids=entity_ids or [],
        evidence_knowledge_ids=kwargs.get("evidence_knowledge_ids", []),
        evidence_entity_ids=kwargs.get("evidence_entity_ids", []),
        metadata=kwargs.get("metadata", {}),
    )
    await belief_store.save(belief)
    metrics.record_belief_created()
    return belief


async def update(belief: Belief) -> None:
    """Update an existing belief. ponytail: caller mutated, we persist."""
    from app.intelligence.metrics import metrics
    belief.updated_at = time.time()
    await belief_store.save(belief)
    # ponytail: update confidence for this belief
    from app.confidence.manager import on_belief_updated
    await on_belief_updated(belief.belief_id)
    # ponytail: refresh opinions that depend on this belief
    from app.opinion.manager import on_belief_updated as opinion_belief_updated
    await opinion_belief_updated(belief.belief_id)
    metrics.record_belief_updated()


async def get(belief_id: str) -> Belief | None:
    return await belief_store.get(belief_id)


async def list_all(state: str = "", limit: int = 100) -> list[Belief]:
    return await belief_store.list_all(state, limit)


async def find_by_entity(entity_id: str) -> list[Belief]:
    """Find all beliefs referencing a WorldEntity."""
    return await belief_store.find_by_entity(entity_id)


async def merge(belief_id: str, other_id: str) -> Belief | None:
    """Merge two beliefs. ponytail: keep belief, absorb other's evidence."""
    from app.intelligence.metrics import metrics

    keep = await belief_store.get(belief_id)
    drop = await belief_store.get(other_id)
    if not keep or not drop:
        return None

    for kid in drop.evidence_knowledge_ids:
        if kid not in keep.evidence_knowledge_ids:
            keep.evidence_knowledge_ids.append(kid)
    for eid in drop.evidence_entity_ids:
        if eid not in keep.evidence_entity_ids:
            keep.evidence_entity_ids.append(eid)
    for eid in drop.entity_ids:
        if eid not in keep.entity_ids:
            keep.entity_ids.append(eid)

    keep.updated_at = time.time()
    await belief_store.save(keep)
    await invalidate(other_id)
    metrics.record_belief_merge()
    return keep


async def attach_evidence(belief_id: str, knowledge_id: str = "", entity_id: str = "") -> Belief | None:
    """Attach supporting evidence to a belief."""
    from app.intelligence.metrics import metrics

    belief = await belief_store.get(belief_id)
    if not belief:
        return None
    if knowledge_id and knowledge_id not in belief.evidence_knowledge_ids:
        belief.evidence_knowledge_ids.append(knowledge_id)
    if entity_id and entity_id not in belief.evidence_entity_ids:
        belief.evidence_entity_ids.append(entity_id)
    belief.updated_at = time.time()
    await belief_store.save(belief)
    metrics.record_belief_updated()
    return belief


async def attach_entity(belief_id: str, entity_id: str) -> Belief | None:
    """Attach a WorldEntity to a belief's subject entities."""
    from app.intelligence.metrics import metrics

    belief = await belief_store.get(belief_id)
    if not belief:
        return None
    if entity_id not in belief.entity_ids:
        belief.entity_ids.append(entity_id)
    belief.updated_at = time.time()
    await belief_store.save(belief)
    metrics.record_belief_updated()
    return belief


async def invalidate(belief_id: str) -> Belief | None:
    """Set belief state to inactive."""
    from app.intelligence.metrics import metrics

    belief = await belief_store.get(belief_id)
    if not belief:
        return None
    belief.state = "inactive"
    belief.updated_at = time.time()
    await belief_store.save(belief)
    metrics.record_belief_invalidated()
    return belief


async def reactivate(belief_id: str) -> Belief | None:
    """Set belief state back to active."""
    from app.intelligence.metrics import metrics

    belief = await belief_store.get(belief_id)
    if not belief:
        return None
    belief.state = "active"
    belief.updated_at = time.time()
    await belief_store.save(belief)
    metrics.record_belief_created()
    return belief


async def on_world_entity_merged(keep_id: str, drop_id: str) -> None:
    """Update beliefs when a WorldEntity is merged. ponytail: redirect entity refs."""
    beliefs = await belief_store.find_by_entity(drop_id)
    for b in beliefs:
        b.entity_ids = [keep_id if eid == drop_id else eid for eid in b.entity_ids]
        b.evidence_entity_ids = [keep_id if eid == drop_id else eid for eid in b.evidence_entity_ids]
        b.updated_at = time.time()
        await belief_store.save(b)


async def on_world_entity_deleted(entity_id: str) -> None:
    """Remove deleted entity references from beliefs. ponytail: drop refs, keep belief."""
    beliefs = await belief_store.find_by_entity(entity_id)
    for b in beliefs:
        b.entity_ids = [eid for eid in b.entity_ids if eid != entity_id]
        b.evidence_entity_ids = [eid for eid in b.evidence_entity_ids if eid != entity_id]
        b.updated_at = time.time()
        await belief_store.save(b)


async def count(state: str = "") -> int:
    return await belief_store.count(state)

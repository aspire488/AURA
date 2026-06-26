from __future__ import annotations

import logging
import time

from app.confidence.confidence import Confidence
from app.confidence.store import confidence_store

logger = logging.getLogger(__name__)


async def create(belief_id: str, value: float = 1.0, **kwargs) -> Confidence:
    """Create confidence for a belief. ponytail: one per belief, dedup by belief_id."""
    # dedup
    existing = await confidence_store.find_by_belief(belief_id)
    if existing:
        return existing
    conf = Confidence(
        belief_id=belief_id,
        value=value,
        evidence_knowledge_ids=kwargs.get("evidence_knowledge_ids", []),
        evidence_observation_ids=kwargs.get("evidence_observation_ids", []),
        metadata=kwargs.get("metadata", {}),
    )
    await confidence_store.save(conf)
    return conf


async def update(confidence: Confidence) -> None:
    """Persist mutated confidence. ponytail: caller mutates fields, we update timestamps."""
    confidence.updated_at = time.time()
    await confidence_store.save(confidence)


async def get(confidence_id: str) -> Confidence | None:
    return await confidence_store.get(confidence_id)


async def list_all(state: str = "", limit: int = 100) -> list[Confidence]:
    return await confidence_store.list_all(state, limit)


async def attach_evidence(confidence_id: str, knowledge_id: str = "", observation_id: str = "") -> Confidence | None:
    """Attach supporting evidence to a confidence record."""
    conf = await confidence_store.get(confidence_id)
    if not conf:
        return None
    if knowledge_id and knowledge_id not in conf.evidence_knowledge_ids:
        conf.evidence_knowledge_ids.append(knowledge_id)
    if observation_id and observation_id not in conf.evidence_observation_ids:
        conf.evidence_observation_ids.append(observation_id)
    await update(conf)
    return conf


async def recompute(confidence_id: str) -> Confidence | None:
    """Recompute confidence value from evidence. ponytail: simple average placeholder."""
    conf = await confidence_store.get(confidence_id)
    if not conf:
        return None
    # naive: average of 1.0 for each evidence piece, else default 1.0
    total = len(conf.evidence_knowledge_ids) + len(conf.evidence_observation_ids)
    conf.value = 1.0 if total == 0 else 0.9  # placeholder simple rule
    await update(conf)
    return conf


async def invalidate(confidence_id: str) -> Confidence | None:
    """Mark confidence as inactive."""
    conf = await confidence_store.get(confidence_id)
    if not conf:
        return None
    conf.state = "inactive"
    await update(conf)
    return conf


async def merge(confidence_id: str, other_id: str) -> Confidence | None:
    """Merge two confidence records, keeping first, absorbing evidence and best value. ponytail: keep higher value."""
    keep = await confidence_store.get(confidence_id)
    drop = await confidence_store.get(other_id)
    if not keep or not drop:
        return None
    # absorb evidence
    for kid in drop.evidence_knowledge_ids:
        if kid not in keep.evidence_knowledge_ids:
            keep.evidence_knowledge_ids.append(kid)
    for oid in drop.evidence_observation_ids:
        if oid not in keep.evidence_observation_ids:
            keep.evidence_observation_ids.append(oid)
    # keep higher value
    keep.value = max(keep.value, drop.value)
    await update(keep)
    await invalidate(other_id)
    return keep


async def on_belief_updated(belief_id: str) -> None:
    """Hook to recompute confidence when belief changes. ponytail: simple call recompute if exists."""
    conf = await confidence_store.find_by_belief(belief_id)
    if conf:
        await recompute(conf.confidence_id)

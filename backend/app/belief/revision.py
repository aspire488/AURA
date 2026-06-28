"""Deterministic Belief Revision.

Consumes Knowledge records and ensures a corresponding Belief exists.
Updates evidence links deterministically without heuristics.

Also provides observation-driven belief calibration: when an Observation
arrives, match it to existing Beliefs, update confidence via Bayesian
scaling, detect contradictions, and create new Beliefs as needed.
"""

from __future__ import annotations

import logging
import time
from typing import List

from app.belief.belief import Belief
from app.belief.manager import (
    create as create_belief,
    attach_evidence as attach_belief_evidence,
    update as update_belief,
)
from app.belief.store import belief_store
from app.confidence.confidence import Confidence
from app.confidence.store import confidence_store
from app.knowledge.store import knowledge_store
from app.observation.observation import Observation

logger = logging.getLogger(__name__)

# ponytail: negation markers for contradiction detection
_NEGATION_MARKERS = {" not ", " never ", " no ", " failed ", "false", "unable", "impossible"}
_STATUS_OPPOSITES = {
    "succeeded": "failed",
    "active": "inactive",
    "true": "false",
    "working": "broken",
    "passing": "failing",
    "online": "offline",
    "enabled": "disabled",
}


def _contradicts(obs_summary: str, belief_statement: str) -> bool:
    """Heuristic contradiction check: negation in obs vs positive belief, or status flip."""
    obs_lower = obs_summary.lower()
    bel_lower = belief_statement.lower()
    # Check negation markers in observation against belief
    for marker in _NEGATION_MARKERS:
        if marker in obs_lower:
            # Strip the negation and check if the remainder matches the belief
            stripped = obs_lower.replace(marker, " ").strip()
            if stripped and _word_overlap(stripped, bel_lower) > 0.3:
                return True
    # Check status opposites
    for pos, neg in _STATUS_OPPOSITES.items():
        if pos in obs_lower and neg in bel_lower:
            return True
        if neg in obs_lower and pos in bel_lower:
            return True
    return False


def _word_overlap(text_a: str, text_b: str) -> float:
    """Jaccard similarity of word sets. ponytail: fast enough for short strings."""
    words_a = set(text_a.split())
    words_b = set(text_b.split())
    if not words_a or not words_b:
        return 0.0
    intersection = words_a & words_b
    union = words_a | words_b
    return len(intersection) / len(union)


def _extract_entity_ids(obs: Observation) -> list[str]:
    """Pull entity references from observation payload. ponytail: check common keys."""
    payload = obs.payload
    entity_ids: list[str] = []
    for key in ("entity_id", "entity_ids", "subject_id", "target_id"):
        val = payload.get(key)
        if isinstance(val, str) and val:
            entity_ids.append(val)
        elif isinstance(val, list):
            entity_ids.extend(v for v in val if isinstance(v, str))
    return entity_ids


def _build_statement(obs: Observation) -> str:
    """Derive a belief statement from observation. ponytail: summary if no structured data."""
    payload = obs.payload
    # Try structured knowledge fields first
    subject = payload.get("subject", "")
    predicate = payload.get("predicate", "")
    obj = payload.get("object", "")
    if subject:
        return f"{subject} {predicate} {obj}".strip() if predicate else subject
    # Fall back to summary
    return obs.summary or f"observation:{obs.observation_id}"


def _bayesian_update(existing_confidence: float, obs_confidence: float) -> float:
    """Deterministic Bayesian-style scaling.

    ponytail: weighted average favoring higher-information source.
    Formula: new = (old * (1 - obs_conf) + obs_conf * obs_conf) 
    Clamped to [0.0, 1.0].
    """
    updated = existing_confidence * (1.0 - obs_confidence) + obs_confidence * obs_confidence
    return max(0.0, min(1.0, updated))


async def process_observation(obs: Observation) -> dict:
    """Process a single Observation into the Belief system.

    1. Match existing beliefs by entity_id or statement overlap.
    2. If match found: Bayesian-update confidence, detect contradictions.
    3. If no match: create new Belief seeded with observation confidence.
    4. Update the separate Confidence table record for the belief.

    Returns a deterministic report dict.
    """
    report: dict = {
        "observation_id": obs.observation_id,
        "action": "none",
        "belief_id": "",
        "confidence_delta": 0.0,
        "contradiction_detected": False,
    }

    entity_ids = _extract_entity_ids(obs)
    statement = _build_statement(obs)
    obs_conf = max(0.0, min(1.0, obs.confidence))

    # --- Step 1: Find matching belief ---
    existing: Belief | None = None

    # Try exact statement match first
    existing = await belief_store.find_by_statement(statement)

    # Try entity match if no statement match
    if not existing:
        for eid in entity_ids:
            beliefs = await belief_store.find_by_entity(eid)
            if beliefs:
                existing = beliefs[0]
                break

    # --- Step 2: Update or create ---
    if existing:
        old_conf = existing.confidence_value
        new_conf = _bayesian_update(old_conf, obs_conf)
        delta = new_conf - old_conf

        # Detect contradiction before updating
        contradicts = _contradicts(obs.summary, existing.statement)
        high_conf_drift = contradicts and old_conf >= 0.7

        # Attach observation as evidence
        if obs.observation_id not in existing.evidence_observation_ids:
            existing.evidence_observation_ids.append(obs.observation_id)
        for eid in entity_ids:
            if eid not in existing.entity_ids:
                existing.entity_ids.append(eid)

        # Update belief confidence
        existing.confidence_value = new_conf
        existing.updated_at = time.time()
        existing.metadata["last_observation_id"] = obs.observation_id
        if contradicts:
            existing.metadata["contradiction_flag"] = True
            existing.metadata["contradiction_observation_id"] = obs.observation_id
        await belief_store.save(existing)

        # Update the Confidence table record
        conf_record = await confidence_store.find_by_belief(existing.belief_id)
        if conf_record:
            conf_record.value = new_conf
            if obs.observation_id not in conf_record.evidence_observation_ids:
                conf_record.evidence_observation_ids.append(obs.observation_id)
            conf_record.updated_at = time.time()
            if high_conf_drift:
                conf_record.metadata["drift_detected"] = True
                conf_record.metadata["drift_observation_id"] = obs.observation_id
            await confidence_store.save(conf_record)
        else:
            # ponytail: create confidence record if missing
            from app.confidence.manager import create as create_confidence
            await create_confidence(
                existing.belief_id,
                value=new_conf,
                evidence_observation_ids=[obs.observation_id],
            )

        report["action"] = "updated"
        report["belief_id"] = existing.belief_id
        report["confidence_delta"] = round(delta, 6)
        report["contradiction_detected"] = contradicts

        # Log high-confidence drift for downstream evaluation
        if high_conf_drift:
            logger.warning(
                "drift_detected: belief=%s (%.2f) contradicted by observation=%s (%.2f)",
                existing.belief_id, old_conf, obs.observation_id, obs_conf,
            )
            # Write drift record into reasoning table for downstream consumption
            _reasoning_metadata = {
                "type": "contradiction_warning",
                "belief_id": existing.belief_id,
                "observation_id": obs.observation_id,
                "old_confidence": old_conf,
                "new_confidence": new_conf,
                "observation_confidence": obs_conf,
            }
            # ponytail: append to belief metadata for now, emit event below
            existing.metadata["drift_record"] = _reasoning_metadata
            await belief_store.save(existing)

            from app.main import emit
            from app.events.event import EventType
            await emit(
                EventType.BELIEF_UPDATED,
                session_id="",
                source="belief_revision/contradiction",
                payload={
                    "belief_id": existing.belief_id,
                    "observation_id": obs.observation_id,
                    "drift_detected": True,
                    "old_confidence": old_conf,
                    "new_confidence": new_conf,
                },
            )
    else:
        # --- Step 3: Create new belief ---
        belief = await create_belief(
            statement,
            entity_ids=entity_ids,
            evidence_knowledge_ids=[],
        )
        belief.confidence_value = obs_conf
        belief.evidence_observation_ids = [obs.observation_id]
        belief.metadata["source_observation_id"] = obs.observation_id
        belief.metadata["source"] = obs.source
        belief.updated_at = time.time()
        await belief_store.save(belief)

        # Create confidence record
        from app.confidence.manager import create as create_confidence
        await create_confidence(
            belief.belief_id,
            value=obs_conf,
            evidence_observation_ids=[obs.observation_id],
        )

        report["action"] = "created"
        report["belief_id"] = belief.belief_id
        report["confidence_delta"] = obs_conf

    return report


async def revise(limit: int = 1000) -> dict:
    """Process recent Knowledge into Beliefs.

    Returns a deterministic report:
        created: number of new beliefs
        updated: number of beliefs strengthened with new evidence
        unchanged: evidence already present
        beliefs: alphabetically sorted list of belief statements processed
    """
    created = updated = unchanged = 0
    processed_statements: List[str] = []

    knowledge_items = await knowledge_store.list_recent(limit=limit)
    for k in knowledge_items:
        statement = k.subject if not (k.predicate or k.object) else f"{k.subject} {k.predicate} {k.object}".strip()
        existing = await belief_store.find_by_statement(statement)
        if not existing:
            await create_belief(statement, evidence_knowledge_ids=[k.knowledge_id])
            created += 1
            processed_statements.append(statement)
        else:
            if k.knowledge_id not in existing.evidence_knowledge_ids:
                await attach_belief_evidence(existing.belief_id, knowledge_id=k.knowledge_id)
                updated += 1
                processed_statements.append(statement)
            else:
                unchanged += 1
    return {
        "created": created,
        "updated": updated,
        "unchanged": unchanged,
        "beliefs": sorted(processed_statements),
    }

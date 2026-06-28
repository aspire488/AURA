from __future__ import annotations

import logging
import time

from app.challenger.challenger import Challenge
from app.challenger.store import challenge_store
from app.reasoning.manager import get as get_reasoning
from app.belief.manager import get as get_belief
from app.opinion.manager import get as get_opinion

logger = logging.getLogger(__name__)

# ponytail: source reliability weights — known authoritative sources score higher
_SOURCE_RELIABILITY = {
    "user_message": 0.6,
    "tool_execution": 0.8,
    "code_execution": 0.85,
    "provider": 0.7,
    "automation_fabric": 0.75,
}
_DEFAULT_SOURCE_RELIABILITY = 0.5


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
    pass


# Simple detection stubs ----------------------------------------------------

async def _detect_conflicting_beliefs(belief_ids: list[str]) -> list[Challenge]:
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
    for ch in await _detect_conflicting_beliefs(reasoning.belief_ids):
        await challenge_store.save(ch)
    for ch in await _detect_contradictory_opinions(reasoning.opinion_ids):
        await challenge_store.save(ch)
    for ch in await _detect_unsupported_reasoning(reasoning_id):
        await challenge_store.save(ch)


async def on_reasoning_updated(reasoning_id: str) -> None:
    """Called when a reasoning record changes. ponytail: trigger evaluation."""
    await evaluate(reasoning_id)


# --- Contradiction resolution pipeline (Subsystem 15) ----------------------

def _provenance_score(obs_timestamp: float, obs_confidence: float, obs_source: str) -> float:
    """Score an observation's provenance strength.

    ponytail: time-decayed confidence weighted by source reliability.
    Score = confidence * source_reliability * time_decay
    time_decay = 1.0 / (1.0 + age_hours / 24)  — halves every 24h
    """
    age_hours = max(0.0, (time.time() - obs_timestamp) / 3600.0)
    time_decay = 1.0 / (1.0 + age_hours / 24.0)
    source_rel = _SOURCE_RELIABILITY.get(obs_source, _DEFAULT_SOURCE_RELIABILITY)
    return obs_confidence * source_rel * time_decay


async def resolve_belief_conflict(belief_id: str, drift_observation_id: str = "") -> dict:
    """Resolve a flagged belief contradiction.

    Loads the belief and its linked observations, scores provenance,
    and either creates a corrective Reasoning or escalates to a Goal.

    Returns a deterministic report.
    """
    from app.belief.store import belief_store
    from app.observation.store import observation_store
    from app.reasoning.manager import create as create_reasoning
    from app.goal.manager import create as create_goal
    from app.confidence.store import confidence_store

    report: dict = {
        "belief_id": belief_id,
        "resolution": "none",
        "challenge_id": "",
        "reasoning_id": "",
        "goal_id": "",
    }

    belief = await belief_store.get(belief_id)
    if not belief:
        return report

    # Gather all observation evidence linked to this belief
    obs_ids = belief.evidence_observation_ids
    if not obs_ids and drift_observation_id:
        obs_ids = [drift_observation_id]

    observations = []
    for oid in obs_ids:
        obs = await observation_store.get(oid)
        if obs:
            observations.append(obs)

    if len(observations) < 2:
        # Need at least two observations to have a conflict
        report["resolution"] = "insufficient_evidence"
        return report

    # Score each observation's provenance
    scored = [
        (_provenance_score(o.timestamp, o.confidence, o.source), o)
        for o in observations
    ]
    scored.sort(key=lambda x: x[0], reverse=True)

    best_score, best_obs = scored[0]
    second_score, second_obs = scored[1]
    delta = best_score - second_score

    # Create a challenge record for this conflict
    challenge = await create(
        typ="conflict_belief",
        target_ids=[belief_id] + [o.observation_id for o in observations],
        description=f"Contradiction in belief {belief_id}: "
        f"best={best_obs.observation_id} ({best_score:.3f}) vs "
        f"second={second_obs.observation_id} ({second_score:.3f}), delta={delta:.3f}",
        metadata={
            "belief_id": belief_id,
            "best_observation_id": best_obs.observation_id,
            "best_score": best_score,
            "second_observation_id": second_obs.observation_id,
            "second_score": second_score,
            "delta": delta,
        },
    )
    report["challenge_id"] = challenge.challenge_id

    # ponytail: threshold — 0.15 delta means one source is clearly stronger
    if delta >= 0.15:
        # Stronger source wins — create corrective reasoning
        entity_label = (belief.entity_ids[0] if belief.entity_ids
                        else belief.statement[:50])
        conclusion = (
            f"Resolved contradiction for belief '{belief.statement}': "
            f"observation {best_obs.observation_id} (score {best_score:.3f}) "
            f"overrides {second_obs.observation_id} (score {second_score:.3f}). "
            f"Source: {best_obs.source}, confidence: {best_obs.confidence:.2f}"
        )
        reasoning = await create_reasoning(
            goal_id="",  # ponytail: no goal needed for direct resolution
            belief_ids=[belief_id],
            metadata={
                "type": "contradiction_resolution",
                "belief_id": belief_id,
                "winning_observation_id": best_obs.observation_id,
                "losing_observation_id": second_obs.observation_id,
                "delta": delta,
            },
        )
        # Override the auto-derived conclusion with our specific one
        reasoning.conclusion = conclusion
        from app.reasoning.store import reasoning_store
        await reasoning_store.save(reasoning)

        # Update belief to reflect the winner
        belief.confidence_value = best_obs.confidence
        belief.metadata["resolved_by"] = best_obs.observation_id
        belief.metadata["resolution_challenge_id"] = challenge.challenge_id
        belief.updated_at = time.time()
        await belief_store.save(belief)

        # Update confidence table
        conf = await confidence_store.find_by_belief(belief_id)
        if conf:
            conf.value = best_obs.confidence
            conf.updated_at = time.time()
            await confidence_store.save(conf)

        report["resolution"] = "resolved_with_reasoning"
        report["reasoning_id"] = reasoning.reasoning_id
        logger.info(
            "Contradiction resolved: belief=%s winner=obs(%s) delta=%.3f",
            belief_id, best_obs.observation_id, delta,
        )
    else:
        # Close match — escalate to investigative goal
        entity_label = (belief.entity_ids[0] if belief.entity_ids
                        else belief.statement[:50])
        goal = await create_goal(
            opinion_ids=[],
            priority=1,
            metadata={
                "type": "resolve_data_discrepancy",
                "belief_id": belief_id,
                "observation_ids": [o.observation_id for o in observations],
                "scores": {o.observation_id: round(s, 3) for s, o in scored},
            },
        )
        # Set goal description via metadata (Goal model has no description field)
        goal.metadata["description"] = (
            f"Resolve data discrepancy regarding {entity_label}: "
            f"observations {[o.observation_id for o in observations]} "
            f"have conflicting provenance (scores: {[round(s, 3) for s, _ in scored]})"
        )
        goal.updated_at = time.time()
        from app.goal.store import goal_store
        await goal_store.save(goal)

        report["resolution"] = "escalated_to_goal"
        report["goal_id"] = goal.goal_id
        logger.info(
            "Contradiction escalated: belief=%s goal=%s scores=%.3f/%.3f",
            belief_id, goal.goal_id, best_score, second_score,
        )

    # Mark challenge as processed
    challenge.state = "resolved"
    challenge.updated_at = time.time()
    await challenge_store.save(challenge)

    return report

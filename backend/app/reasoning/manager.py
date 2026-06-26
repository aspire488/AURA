from __future__ import annotations

import logging
import time

from app.reasoning.reasoning import Reasoning
from app.reasoning.store import reasoning_store
from app.goal.manager import get as get_goal
from app.opinion.manager import get as get_opinion
from app.belief.manager import get as get_belief
from app.intelligence.metrics import metrics

logger = logging.getLogger(__name__)


async def create(goal_id: str, belief_ids: list[str] | None = None, opinion_ids: list[str] | None = None, **kwargs) -> Reasoning:
    """Create a reasoning record. ponytail: dedup by exact goal+belief+opinion set."""
    # Check for existing identical reasoning
    existing = await reasoning_store.find_by_goal(goal_id)
    for r in existing:
        if set(r.belief_ids) == set(belief_ids or []) and set(r.opinion_ids) == set(opinion_ids or []):
            return r
    reasoning = Reasoning(
        goal_id=goal_id,
        belief_ids=belief_ids or [],
        opinion_ids=opinion_ids or [],
        metadata=kwargs.get("metadata", {}),
    )
    # Derive conclusion immediately
    await derive(reasoning.reasoning_id)
    await reasoning_store.save(reasoning)
    metrics.record_reasoning(pipeline_latency_ms=0.0, provider_latency_ms=0.0, prompt_tokens=0, completion_tokens=0)
    return reasoning


async def get(reasoning_id: str) -> Reasoning | None:
    return await reasoning_store.get(reasoning_id)


async def list_all(state: str = "", limit: int = 100) -> list[Reasoning]:
    return await reasoning_store.list_all(state, limit)


async def update(reasoning: Reasoning) -> None:
    """Persist mutated reasoning. ponytail: caller updates fields, we refresh timestamp and trigger challenge eval."""
    reasoning.updated_at = time.time()
    await reasoning_store.save(reasoning)
    # ponytail: notify challenger of updated reasoning
    from app.challenger.manager import on_reasoning_updated
    await on_reasoning_updated(reasoning.reasoning_id)


async def invalidate(reasoning_id: str) -> Reasoning | None:
    reasoning = await reasoning_store.get(reasoning_id)
    if not reasoning:
        return None
    reasoning.state = "inactive"
    await update(reasoning)
    return reasoning


async def merge(reasoning_id: str, other_id: str) -> Reasoning | None:
    """Merge two reasonings, keep first, union refs, concatenate conclusions."""
    keep = await reasoning_store.get(reasoning_id)
    drop = await reasoning_store.get(other_id)
    if not keep or not drop:
        return None
    keep.belief_ids = sorted(set(keep.belief_ids) | set(drop.belief_ids))
    keep.opinion_ids = sorted(set(keep.opinion_ids) | set(drop.opinion_ids))
    if drop.conclusion:
        keep.conclusion = (keep.conclusion + " \n" + drop.conclusion).strip()
    await update(keep)
    await invalidate(other_id)
    return keep


async def derive(reasoning_id: str) -> Reasoning | None:
    """Derive a simple textual conclusion from goal, opinions, and beliefs. ponytail: concatenate texts."""
    reasoning = await reasoning_store.get(reasoning_id)
    if not reasoning:
        return None
    # fetch goal for context (minimal use)
    goal = await get_goal(reasoning.goal_id)
    # fetch opinions and beliefs for IDs - we only need counts
    opinion_vals = []
    for oid in reasoning.opinion_ids:
        op = await get_opinion(oid)
        if op:
            opinion_vals.append(op.value)
    belief_texts = []
    for bid in reasoning.belief_ids:
        b = await get_belief(bid)
        if b:
            belief_texts.append(b.statement)
    avg_opinion = (sum(opinion_vals) / len(opinion_vals)) if opinion_vals else 0.0
    conclusion = f"Goal {reasoning.goal_id}" + (
        f" (priority {goal.priority})" if goal else ""
    ) + f"; avg opinion {avg_opinion:.2f}; beliefs: {'; '.join(belief_texts)}"
    reasoning.conclusion = conclusion
    await update(reasoning)
    return reasoning

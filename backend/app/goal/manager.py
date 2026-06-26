from __future__ import annotations

import time

from app.goal.goal import Goal
from app.goal.store import goal_store

# Creation dedup by exact opinion set
async def create(opinion_ids: list[str], priority: int = 0, **kwargs) -> Goal:
    """Create a goal from a set of opinion IDs. ponytail: dedup exact set."""
    # ponytail: skip dedup, always insert new goal
    # existing = await goal_store.find_by_exact_opinions(opinion_ids)
    # if existing:
    #     return existing
    goal = Goal(
        supporting_opinion_ids=sorted(set(opinion_ids)),
        priority=priority,
        metadata=kwargs.get("metadata", {}),
    )
    await goal_store.save(goal)
    return goal

async def update(goal: Goal) -> None:
    """Persist mutated goal. ponytail: caller mutates, we update timestamp."""
    goal.updated_at = time.time()
    await goal_store.save(goal)

async def get(goal_id: str) -> Goal | None:
    return await goal_store.get(goal_id)

async def list_all(status: str = "", limit: int = 100) -> list[Goal]:
    return await goal_store.list_all(status, limit)

async def merge(goal_id: str, other_id: str) -> Goal | None:
    """Merge two goals, keep first, union opinion refs, keep higher priority."""
    keep = await goal_store.get(goal_id)
    drop = await goal_store.get(other_id)
    if not keep or not drop:
        return None
    keep.supporting_opinion_ids = sorted(set(keep.supporting_opinion_ids) | set(drop.supporting_opinion_ids))
    keep.priority = max(keep.priority, drop.priority)
    await update(keep)
    await invalidate(other_id)
    return keep

async def set_status(goal_id: str, status: str) -> Goal | None:
    goal = await goal_store.get(goal_id)
    if not goal:
        return None
    goal.status = status
    await update(goal)
    return goal

async def activate(goal_id: str) -> Goal | None:
    return await set_status(goal_id, "active")

async def pause(goal_id: str) -> Goal | None:
    return await set_status(goal_id, "paused")

async def complete(goal_id: str) -> Goal | None:
    return await set_status(goal_id, "completed")

async def abandon(goal_id: str) -> Goal | None:
    return await set_status(goal_id, "abandoned")

async def invalidate(goal_id: str) -> Goal | None:
    return await set_status(goal_id, "invalid")

# Derive goal from opinions (same as create but explicit name)
async def derive_from_opinions(opinion_ids: list[str], priority: int = 0, **kwargs) -> Goal:
    return await create(opinion_ids, priority, **kwargs)

# Hook: when an opinion updates, refresh related goals (placeholder)
async def on_opinion_updated(opinion_id: str) -> None:
    """Refresh any goals that reference this opinion."""
    goals = await goal_store.find_by_opinion(opinion_id)
    for g in goals:
        await update(g)

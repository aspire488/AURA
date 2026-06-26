"""Planning manager – CRUD and deterministic plan generation.

Follows the minimal patterns of Goal and Oracle managers.
"""

from __future__ import annotations

import time
from typing import List

from app.planning.plan import Plan
from app.planning.store import plan_store

# CRUD ---------------------------------------------------------------------

async def create(
    goal_ids: List[str] | None = None,
    decision_ids: List[str] | None = None,
    priority: int = 0,
    **kwargs,
) -> Plan:
    """Create a plan linking goals and decisions.
    ponytail: no dedup – each plan unique; caller can de‑duplicate if needed.
    """
    goal_ids = sorted(set(goal_ids or []))
    decision_ids = sorted(set(decision_ids or []))
    plan = Plan(
        goal_ids=goal_ids,
        decision_ids=decision_ids,
        priority=priority,
        metadata=kwargs.get("metadata", {}),
    )
    await plan_store.save(plan)
    return plan

async def get(plan_id: str) -> Plan | None:
    return await plan_store.get(plan_id)

async def list_all(status: str = "", limit: int = 100) -> List[Plan]:
    return await plan_store.list_all(status, limit)

async def update(plan: Plan) -> None:
    """Persist mutated plan. Caller modifies fields; we refresh timestamp."""
    plan.updated_at = time.time()
    await plan_store.save(plan)

async def set_status(plan_id: str, status: str) -> Plan | None:
    plan = await plan_store.get(plan_id)
    if not plan:
        return None
    plan.status = status
    await update(plan)
    return plan

async def activate(plan_id: str) -> Plan | None:
    return await set_status(plan_id, "active")

async def pause(plan_id: str) -> Plan | None:
    return await set_status(plan_id, "paused")

async def complete(plan_id: str) -> Plan | None:
    plan = await set_status(plan_id, "completed")
    # ponytail: create/refresh reflection on completion
    if plan:
        from app.reflection.manager import refresh_for_plan
        await refresh_for_plan(plan_id)
    return plan

async def invalidate(plan_id: str) -> Plan | None:
    return await plan_store.invalidate(plan_id)

# Merge --------------------------------------------------------------------

async def merge(plan_id: str, other_id: str) -> Plan | None:
    """Merge two plans: keep first, union IDs, higher priority, combine actions.
    ponytail: simple union, actions concatenated.
    """
    keep = await plan_store.get(plan_id)
    drop = await plan_store.get(other_id)
    if not keep or not drop:
        return None
    keep.goal_ids = sorted(set(keep.goal_ids + drop.goal_ids))
    keep.decision_ids = sorted(set(keep.decision_ids + drop.decision_ids))
    keep.priority = max(keep.priority, drop.priority)
    # combine action sequences preserving order
    keep.action_sequence = keep.action_sequence + [a for a in drop.action_sequence if a not in keep.action_sequence]
    await update(keep)
    await invalidate(other_id)
    return keep

# Deterministic action generation ------------------------------------------

async def generate_action_sequence(plan_id: str) -> Plan | None:
    """Populate a deterministic action sequence based on linked goals and decisions.
    ponytail: simple deterministic strings; sorted IDs ensure repeatability.
    """
    plan = await plan_store.get(plan_id)
    if not plan:
        return None
    actions = []
    for gid in sorted(plan.goal_ids):
        actions.append(f"execute_goal_{gid}")
    for did in sorted(plan.decision_ids):
        actions.append(f"apply_decision_{did}")
    plan.action_sequence = actions
    await update(plan)
    return plan

# Hook: refresh when a linked decision changes ----------------------------

async def on_decision_updated(decision_id: str) -> None:
    """Regenerate action sequences for any plans referencing this decision."""
    plans = await plan_store.find_by_decision(decision_id)
    for p in plans:
        await generate_action_sequence(p.plan_id)

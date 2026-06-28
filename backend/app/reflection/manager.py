"""Reflection manager – CRUD and hooks.

Follows pattern of Goal/Planning managers, minimal implementation.
"""

from __future__ import annotations

import time
from typing import List

from app.reflection.reflection import Reflection
from app.reflection.store import reflection_store
from app.planning.store import plan_store

# CRUD ---------------------------------------------------------------------

async def create(
    plan_id: str | None = None,
    decision_ids: List[str] | None = None,
    reasoning_ids: List[str] | None = None,
    strengths: List[str] | None = None,
    weaknesses: List[str] | None = None,
    suggestions: List[str] | None = None,
    **kwargs,
) -> Reflection:
    """Create a new reflection record.
    ponytail: simple union of provided lists, no dedup beyond set.
    """
    reflection = Reflection(
        plan_id=plan_id,
        decision_ids=sorted(set(decision_ids or [])),
        reasoning_ids=sorted(set(reasoning_ids or [])),
        strengths=sorted(set(strengths or [])),
        weaknesses=sorted(set(weaknesses or [])),
        suggestions=sorted(set(suggestions or [])),
        metadata=kwargs.get("metadata", {}),
    )
    await reflection_store.save(reflection)
    
    return reflection

async def get(reflection_id: str) -> Reflection | None:
    return await reflection_store.get(reflection_id)

async def list_all(status: str = "", limit: int = 100) -> List[Reflection]:
    return await reflection_store.list_all(status, limit)

async def update(reflection: Reflection) -> None:
    """Persist mutated reflection. Refresh timestamp."""
    reflection.updated_at = time.time()
    await reflection_store.save(reflection)

async def invalidate(reflection_id: str) -> Reflection | None:
    return await reflection_store.invalidate(reflection_id)

# Merge --------------------------------------------------------------------

async def merge(target_id: str, source_id: str) -> Reflection | None:
    return await reflection_store.merge(target_id, source_id)

# Hook: ensure reflection exists for completed plans -----------------------

async def refresh_for_plan(plan_id: str) -> Reflection:
    """Create or update a reflection when a plan is completed.
    Simple implementation: one reflection per plan.
    """
    # check existing
    existing = await reflection_store.find_by_plan(plan_id)
    if existing:
        reflection = existing[0]
        reflection.updated_at = time.time()
        await reflection_store.save(reflection)
        
        return reflection
    # create new
    plan = await plan_store.get(plan_id)
    decision_ids = getattr(plan, "decision_ids", []) if plan else []
    reflection = await create(plan_id=plan_id, decision_ids=decision_ids)
    return reflection

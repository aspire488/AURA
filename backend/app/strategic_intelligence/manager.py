"""Strategic Intelligence manager – deterministic, event‑driven insights.

Collects high‑level metrics from existing stores, computes deterministic
strategic scores, and keeps an in‑memory snapshot of current insights.
All calculations use explicit formulas – no heuristics, no LLMs.
"""

from __future__ import annotations

import time
import math
from typing import Any, Dict

from app.events.event import BaseEvent, EventType
from app.emergence.manager import (
    aggregate_subsystem_outputs,
    identify_recurring_patterns,
)

# in‑memory state – lightweight, no persistence
_last_snapshot: Dict[str, Any] = {}
_insights: Dict[str, Any] = {}

def _growth(delta: float, dt: float) -> float:
    return delta / dt if dt else 0.0

def _momentum(delta: int, dt: float) -> float:
    return delta / dt if dt else 0.0

def _relationship_strength(interactions: int, confidence: float, recency: float) -> float:
    return interactions * confidence * math.exp(-0.001 * recency)

def _automation_opportunity(reps: int, latency: float, prob: float) -> float:
    return reps * latency * prob

async def _update_snapshot() -> None:
    now = time.time()
    # Safely fetch subsystem counts – DB may be unavailable in test env.
    try:
        raw = await aggregate_subsystem_outputs()
    except Exception:
        raw = {}
    prev = _last_snapshot.get("counts", {})
    dt = now - _last_snapshot.get("timestamp", now)

    knowledge_delta = raw.get("knowledge_items", 0) - prev.get("knowledge_items", 0)
    knowledge_growth = _growth(knowledge_delta, dt)

    goal_delta = raw.get("goals", 0) - prev.get("goals", 0)
    goal_momentum = _momentum(goal_delta, dt)

    try:
        patterns = await identify_recurring_patterns(limit=10)
    except Exception:
        patterns = []
    rel_strength = _relationship_strength(len(patterns), 1.0, dt)

    from app.runtime.tool_registry import _tool_stats
    automation_score = 0.0
    for s in _tool_stats.values():
        reps = s.get("execution_count", 0)
        avg_latency = (s.get("total_latency_ms", 0.0) / reps) if reps else 0.0
        prob = (s.get("success_count", 0) / reps) if reps else 0.0
        automation_score += _automation_opportunity(reps, avg_latency, prob)

    # --------------------
    # Deterministic thresholds (pony-tail: tune via config if needed)
    # --------------------
    _KG_THRESHOLD = 0.1  # knowledge growth per sec
    _GM_THRESHOLD = 0.05  # goal momentum per sec
    _RS_THRESHOLD = 0.2   # relationship strength
    _AO_THRESHOLD = 5.0   # automation opportunity score

    # Trigger actions based on thresholds
    if knowledge_growth > _KG_THRESHOLD:
        await _trigger_knowledge_growth_goal(knowledge_growth)
    if goal_momentum > _GM_THRESHOLD:
        await _trigger_goal_momentum_goal(goal_momentum)
    if rel_strength > _RS_THRESHOLD:
        await _trigger_relationship_strength_action(rel_strength)
    if automation_score > _AO_THRESHOLD:
        await _trigger_automation_opportunity_action(automation_score)

    global _insights
    _insights = {
        "knowledge_growth_per_sec": knowledge_growth,
        "goal_momentum_per_sec": goal_momentum,
        "relationship_strength": rel_strength,
        "automation_opportunity_score": automation_score,
        "timestamp": now,
    }

    # Persist strategic snapshot in continuity (single session id)
    try:
        from app.continuity.manager import get_or_create, update_state
        cont = await get_or_create("strategic")
        await update_state(cont.continuity_id, _insights)
    except Exception:
        pass  # ignore if continuity store unavailable

    _last_snapshot["counts"] = raw
    _last_snapshot["timestamp"] = now

async def process_event(event: BaseEvent) -> None:
    strategic = {
        EventType.CODE_EXECUTED,
        EventType.REFLECTION_CREATED,
        EventType.GOAL_UPDATED,
        EventType.OBSERVATION_INGESTED,
        EventType.KNOWLEDGE_CREATED,
    }
    if event.event_type in strategic:
        await _update_snapshot()

def get_current_insights() -> Dict[str, Any]:
    return _insights.copy()

# --------------------
# Action helpers (deterministic triggers)
# --------------------

async def _trigger_knowledge_growth_goal(value: float) -> None:
    """Create a goal when knowledge growth exceeds threshold."""
    from app.goal.store import goal_store
    from app.goal.goal import Goal
    import uuid
    goal = Goal(
        goal_id=uuid.uuid4().hex[:12],
        status="active",
        priority=6,
        metadata={
            "category": "knowledge_growth",
            "trigger": "strategic_insight",
            "value": value,
        },
    )
    await goal_store.save(goal)
    from app.main import emit
    await emit("goal_created", session_id="strategic", source="strategic_intelligence", payload=goal.model_dump())

async def _trigger_goal_momentum_goal(value: float) -> None:
    """Create a goal when goal momentum exceeds threshold."""
    from app.goal.store import goal_store
    from app.goal.goal import Goal
    import uuid
    goal = Goal(
        goal_id=uuid.uuid4().hex[:12],
        status="active",
        priority=5,
        metadata={
            "category": "goal_momentum",
            "trigger": "strategic_insight",
            "value": value,
        },
    )
    await goal_store.save(goal)
    from app.main import emit
    await emit("goal_created", session_id="strategic", source="strategic_intelligence", payload=goal.model_dump())

async def _trigger_relationship_strength_action(value: float) -> None:
    """Invoke stewardship repair on relationship issues when strength high."""
    from app.stewardship.manager import repair_orphan_relationships
    await repair_orphan_relationships()

async def _trigger_automation_opportunity_action(value: float) -> None:
    """Dispatch automation via proactivity manager when opportunity high."""
    from app.runtime.proactivity_manager import proactivity_manager
    await proactivity_manager._dispatch_automation(
        category="automation_opportunity",
        target_node="generic_automation",
        params={"score": value},
        session_id="strategic",
    )


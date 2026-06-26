"""Proactivity manager – deterministic triggers for opportunities and stalled goals.

Implemented as pure functions; no DB persistence needed for this minimal runtime.

Extended lightweight proactivity features: opportunity, stalled goal, inactive project
 detection, follow‑up recommendations, knowledge‑gap detection, low‑confidence
 hotspot detection, recurring‑interest detection, deterministic priority scoring,
 cooldown windows, trigger deduplication, and an in‑memory suggestion queue.
"""

from __future__ import annotations

from typing import List

from app.reflection.reflection import Reflection
from app.goal.manager import list_all as list_goals


async def detect_opportunities() -> List[str]:
    """Return a list of simple opportunity strings.
    ponytail: placeholder – returns empty list; extend when needed.
    """
    # In a full system this would analyze reflections and goals.
    return []

# --- new proactivity helpers ---
from app.identity.manager import get_identity_manager
from app.confidence.manager import list_all as list_confidences
from datetime import datetime, timezone
import hashlib

# In‑memory suggestion queue and cooldown tracking
_suggestion_queue: List[tuple[str, float]] = []  # (suggestion, priority)
_cooldown_tracker: dict[str, float] = {}  # suggestion -> last timestamp

def _hash_suggestion(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()

def _deterministic_priority(suggestion: str) -> float:
    # Simple deterministic score 0..1 based on hash
    h = int(_hash_suggestion(suggestion), 16)
    return (h % 1000) / 1000.0

async def add_suggestion(suggestion: str) -> None:
    """Add suggestion to queue with deterministic priority, respecting cooldown.
    ponytail: dedup via hash, cooldown 60 s default.
    """
    now = datetime.now(timezone.utc).timestamp()
    key = _hash_suggestion(suggestion)
    last = _cooldown_tracker.get(key, 0)
    if now - last < 60:
        return  # within cooldown, ignore
    _cooldown_tracker[key] = now
    priority = _deterministic_priority(suggestion)
    _suggestion_queue.append((suggestion, priority))

async def pop_suggestion() -> tuple[str, float] | None:
    """Pop highest‑priority suggestion.
    ponytail: simple linear scan, O(n).
    """
    if not _suggestion_queue:
        return None
    # find max priority
    idx = max(range(len(_suggestion_queue)), key=lambda i: _suggestion_queue[i][1])
    return _suggestion_queue.pop(idx)

async def detect_inactive_projects() -> List[str]:
    """Detect projects with no recent activity (no `last_seen` metadata in 7 days).
    ponytail: simple heuristic based on metadata timestamp.
    """
    manager = get_identity_manager()
    projects = await manager.list_projects()
    inactive = []
    week_ago = datetime.now(timezone.utc).timestamp() - 7 * 86400
    for p in projects:
        last = p.metadata.get("last_activity", p.created_at)
        if last < week_ago:
            inactive.append(p.project_id)
    return inactive

async def generate_followup_recommendations() -> List[str]:
    """Combine stalled goals and inactive projects into follow‑up suggestions.
    ponytail: naive concatenation.
    """
    stalled = await detect_stalled_goals()
    inactive = await detect_inactive_projects()
    suggestions = []
    for gid in stalled:
        suggestions.append(f"Review stalled goal {gid}")
    for pid in inactive:
        suggestions.append(f"Revive inactive project {pid}")
    for s in suggestions:
        await add_suggestion(s)
    return suggestions

async def detect_knowledge_gaps() -> List[str]:
    """Identify gaps where recent reflections have no associated knowledge.
    ponytail: placeholder – returns empty list.
    """
    # Could compare Reflection timestamps vs knowledge count; omitted for brevity.
    return []

async def detect_low_confidence_hotspots(threshold: float = 0.3) -> List[str]:
    """Find confidences below *threshold*.
    ponytail: simple filter.
    """
    all_conf = await list_confidences()
    low = [c.confidence_id for c in all_conf if c.value < threshold]
    return low

async def detect_recurring_interests() -> List[str]:
    """Detect repeated opportunity strings (simple dedup by hash).
    ponytail: placeholder – returns empty list.
    """
    return []


async def detect_stalled_goals() -> List[str]:
    """Return IDs of goals that have no recent activity.
    ponytail: naive – goals with status not 'active' are considered stalled.
    """
    stalled = []
    goals = await list_goals(status="", limit=1000)  # get all goals
    for g in goals:
        if getattr(g, "status", "") != "active":
            stalled.append(g.goal_id)
    return stalled

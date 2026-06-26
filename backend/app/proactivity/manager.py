"""Proactivity manager – deterministic triggers for opportunities and stalled goals.

Implemented as pure functions; no DB persistence needed for this minimal runtime.
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

"""Stable Knowledge Promotion.

Consumes stable learning candidates (from Learning Aggregation) and promotes them to
Knowledge records when they are not already present.
"""

from __future__ import annotations

from app.knowledge.knowledge import Knowledge
from app.knowledge.store import knowledge_store
from app.learning.manager import aggregate_stable_lessons


# ponytail: minimal deterministic promotion – exact string matching only
async def promote_stable_lessons(threshold: int = 3) -> dict:
    """Promote stable lessons to Knowledge.

    Returns a deterministic report:
        * ``promoted_count`` – number of newly created Knowledge records
        * ``skipped_count`` – number of lessons already present
        * ``promoted_lessons`` – alphabetically sorted list of lesson strings promoted
        * ``skipped_lessons`` – alphabetically sorted list of lesson strings skipped
    """
    stable = await aggregate_stable_lessons(threshold=threshold)
    promoted: list[str] = []
    skipped: list[str] = []
    for entry in stable:
        lesson = entry["lesson"]
        # exact duplicate check – subject matches lesson, predicate and object empty
        existing = await knowledge_store.find_duplicate(subject=lesson, predicate="", obj="")
        if existing:
            skipped.append(lesson)
            continue
        knowledge = Knowledge(
            subject=lesson,
            metadata={"reflection_ids": entry["reflection_ids"]},
        )
        await knowledge_store.append(knowledge)
        promoted.append(lesson)
    promoted.sort()
    skipped.sort()
    return {
        "promoted_count": len(promoted),
        "skipped_count": len(skipped),
        "promoted_lessons": promoted,
        "skipped_lessons": skipped,
    }

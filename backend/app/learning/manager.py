"""Learning manager – create learning from reflections.

Provides deterministic CRUD and a tiny ``derive_lessons`` helper that turns a
Reflection's strengths/weaknesses into simple lesson strings.
"""

from __future__ import annotations

import time

from app.learning.model import Learning
from app.learning.store import learning_store
from app.reflection.reflection import Reflection


async def derive_lessons(reflection: Reflection) -> list[str]:
    """Derive simplistic lessons from a reflection.
    ponytail: concatenate strengths and weaknesses.
    """
    lessons = []
    if reflection.strengths:
        lessons.append("strengths: " + ", ".join(reflection.strengths))
    if reflection.weaknesses:
        lessons.append("weaknesses: " + ", ".join(reflection.weaknesses))
    return lessons


async def create_from_reflection(reflection: Reflection, **kwargs) -> Learning:
    """Create a learning record for *reflection*.
    ponytail: idempotent – if a record already exists for the same reflection, return it.
    """
    existing = await learning_store.find_by_reflection(reflection.reflection_id)
    if existing:
        return existing

    lessons = await derive_lessons(reflection)
    learning = Learning(
        reflection_id=reflection.reflection_id,
        lessons=lessons,
        metadata=kwargs.get("metadata", {}),
    )
    await learning_store.save(learning)
    return learning


async def get(learning_id: str) -> Learning | None:
    return await learning_store.get(learning_id)


async def list_all(limit: int = 100) -> list[Learning]:
    return await learning_store.list_all(limit)

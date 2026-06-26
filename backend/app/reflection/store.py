"""PostgreSQL‑backed persistence for Reflection records.

Mirrors other stores; uses raw SQL, no extra deps.
"""

from __future__ import annotations

import json
import logging
import time
from typing import List

from sqlalchemy import text

from app.reflection.reflection import Reflection
from app.substrate.postgres.client import get_session

logger = logging.getLogger(__name__)

CREATE_REFLECTION_TABLE = """
CREATE TABLE IF NOT EXISTS reflections (
    reflection_id VARCHAR(12) PRIMARY KEY,
    plan_id VARCHAR(12),
    decision_ids JSONB DEFAULT '[]',
    reasoning_ids JSONB DEFAULT '[]',
    strengths JSONB DEFAULT '[]',
    weaknesses JSONB DEFAULT '[]',
    suggestions JSONB DEFAULT '[]',
    status VARCHAR(16) DEFAULT 'active',
    created_at DOUBLE PRECISION NOT NULL,
    updated_at DOUBLE PRECISION NOT NULL,
    metadata JSONB DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS idx_reflection_plan ON reflections(plan_id);
"""


class ReflectionStore:
    """Raw‑SQL store for Reflection records. ponytail: copy pattern of other stores."""

    async def initialize(self) -> None:
        try:
            async with get_session() as session:
                for stmt in CREATE_REFLECTION_TABLE.strip().split(";"):
                    stmt = stmt.strip()
                    if stmt:
                        await session.execute(text(stmt))
                await session.commit()
            logger.info("Reflection table ready")
        except Exception:
            logger.exception("Failed to initialize reflection table")

    async def save(self, reflection: Reflection) -> None:
        try:
            async with get_session() as session:
                await session.execute(
                    text(
                        "INSERT INTO reflections (reflection_id, plan_id, decision_ids, reasoning_ids, strengths, weaknesses, suggestions, status, created_at, updated_at, metadata) "
                        "VALUES (:rid, :pid, :decisions, :reasonings, :strengths, :weaknesses, :suggestions, :status, :created, :updated, :meta) "
                        "ON CONFLICT (reflection_id) DO UPDATE SET "
                        "plan_id = EXCLUDED.plan_id, decision_ids = EXCLUDED.decision_ids, reasoning_ids = EXCLUDED.reasoning_ids, "
                        "strengths = EXCLUDED.strengths, weaknesses = EXCLUDED.weaknesses, suggestions = EXCLUDED.suggestions, "
                        "status = EXCLUDED.status, updated_at = EXCLUDED.updated_at, metadata = EXCLUDED.metadata"
                    ),
                    {
                        "rid": reflection.reflection_id,
                        "pid": reflection.plan_id,
                        "decisions": json.dumps(reflection.decision_ids),
                        "reasonings": json.dumps(reflection.reasoning_ids),
                        "strengths": json.dumps(reflection.strengths),
                        "weaknesses": json.dumps(reflection.weaknesses),
                        "suggestions": json.dumps(reflection.suggestions),
                        "status": reflection.status,
                        "created": reflection.created_at,
                        "updated": reflection.updated_at,
                        "meta": json.dumps(reflection.metadata),
                    },
                )
                await session.commit()
        # ponytail: after persisting reflection, derive learning
        from app.reflection.reflection import process_reflection
        await process_reflection(reflection)
        except Exception:
            logger.exception("Failed to save reflection %s", reflection.reflection_id)

    async def get(self, reflection_id: str) -> Reflection | None:
        async with get_session() as session:
            result = await session.execute(
                text("SELECT * FROM reflections WHERE reflection_id = :rid"), {"rid": reflection_id}
            )
            row = result.mappings().first()
            return self._row_to_reflection(row) if row else None

    async def list_all(self, status: str = "", limit: int = 100) -> List[Reflection]:
        async with get_session() as session:
            if status:
                result = await session.execute(
                    text("SELECT * FROM reflections WHERE status = :status ORDER BY created_at DESC LIMIT :limit"),
                    {"status": status, "limit": limit},
                )
            else:
                result = await session.execute(
                    text("SELECT * FROM reflections ORDER BY created_at DESC LIMIT :limit"), {"limit": limit}
                )
            return [self._row_to_reflection(row) for row in result.mappings()]

    async def find_by_plan(self, plan_id: str) -> List[Reflection]:
        async with get_session() as session:
            result = await session.execute(
                text("SELECT * FROM reflections WHERE plan_id = :pid"), {"pid": plan_id}
            )
            return [self._row_to_reflection(row) for row in result.mappings()]

    async def invalidate(self, reflection_id: str) -> Reflection | None:
        reflection = await self.get(reflection_id)
        if not reflection:
            return None
        reflection.status = "invalid"
        reflection.updated_at = time.time()
        await self.save(reflection)
        return reflection

    async def merge(self, target_id: str, source_id: str) -> Reflection | None:
        """Merge source into target; union list fields, keep newer timestamps."""
        target = await self.get(target_id)
        source = await self.get(source_id)
        if not target or not source:
            return None
        # union list fields
        target.decision_ids = sorted(set(target.decision_ids + source.decision_ids))
        target.reasoning_ids = sorted(set(target.reasoning_ids + source.reasoning_ids))
        target.strengths = sorted(set(target.strengths + source.strengths))
        target.weaknesses = sorted(set(target.weaknesses + source.weaknesses))
        target.suggestions = sorted(set(target.suggestions + source.suggestions))
        target.updated_at = time.time()
        await self.save(target)
        await self.invalidate(source_id)
        return target

    def _row_to_reflection(self, row: dict) -> Reflection:
        def _load(key, default):
            val = row.get(key)
            if isinstance(val, str):
                return json.loads(val)
            return val or default

        return Reflection(
            reflection_id=row["reflection_id"],
            plan_id=row.get("plan_id"),
            decision_ids=_load("decision_ids", []),
            reasoning_ids=_load("reasoning_ids", []),
            strengths=_load("strengths", []),
            weaknesses=_load("weaknesses", []),
            suggestions=_load("suggestions", []),
            status=row.get("status", "active"),
            created_at=row["created_at"],
            updated_at=row.get("updated_at", row["created_at"]),
            metadata=_load("metadata", {}),
        )


reflection_store = ReflectionStore()

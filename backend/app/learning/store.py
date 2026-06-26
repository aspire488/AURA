"""Learning store – PostgreSQL persistence for Learning records.

Follows the minimal raw‑SQL pattern used throughout the codebase.
"""

from __future__ import annotations

import json
import logging

from sqlalchemy import text

from app.learning.model import Learning
from app.substrate.postgres.client import get_session

logger = logging.getLogger(__name__)

CREATE_LEARNING_TABLE = """
CREATE TABLE IF NOT EXISTS learnings (
    learning_id VARCHAR(12) PRIMARY KEY,
    reflection_id VARCHAR(12) NOT NULL,
    lessons JSONB DEFAULT '[]',
    created_at DOUBLE PRECISION NOT NULL,
    updated_at DOUBLE PRECISION NOT NULL,
    metadata JSONB DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS idx_learning_reflection ON learnings(reflection_id);
"""


class LearningStore:
    """Raw‑SQL store for :class:`Learning`.
    ponytail: simple upsert, no ORM.
    """

    async def initialize(self) -> None:
        async with get_session() as session:
            for stmt in CREATE_LEARNING_TABLE.strip().split(";"):
                stmt = stmt.strip()
                if stmt:
                    await session.execute(text(stmt))
            await session.commit()
        logger.info("Learning table ready")

    async def save(self, learning: Learning) -> None:
        async with get_session() as session:
            await session.execute(
                text(
                    "INSERT INTO learnings (learning_id, reflection_id, lessons, created_at, updated_at, metadata) "
                    "VALUES (:lid, :rid, :lessons, :created, :updated, :meta) "
                    "ON CONFLICT (learning_id) DO UPDATE SET "
                    "reflection_id=EXCLUDED.reflection_id, lessons=EXCLUDED.lessons, "
                    "updated_at=EXCLUDED.updated_at, metadata=EXCLUDED.metadata"
                ),
                {
                    "lid": learning.learning_id,
                    "rid": learning.reflection_id,
                    "lessons": json.dumps(learning.lessons),
                    "created": learning.created_at,
                    "updated": learning.updated_at,
                    "meta": json.dumps(learning.metadata),
                },
            )
            await session.commit()

    async def get(self, learning_id: str) -> Learning | None:
        async with get_session() as session:
            result = await session.execute(
                text("SELECT * FROM learnings WHERE learning_id = :lid"), {"lid": learning_id}
            )
            row = result.mappings().first()
            return self._row_to_learning(row) if row else None

    async def list_all(self, limit: int = 100) -> list[Learning]:
        async with get_session() as session:
            result = await session.execute(
                text("SELECT * FROM learnings ORDER BY created_at DESC LIMIT :limit"), {"limit": limit}
            )
            return [self._row_to_learning(row) for row in result.mappings()]

    async def find_by_reflection(self, reflection_id: str) -> Learning | None:
        async with get_session() as session:
            result = await session.execute(
                text("SELECT * FROM learnings WHERE reflection_id = :rid LIMIT 1"), {"rid": reflection_id}
            )
            row = result.mappings().first()
            return self._row_to_learning(row) if row else None

    def _row_to_learning(self, row: dict) -> Learning:
        return Learning(
            learning_id=row["learning_id"],
            reflection_id=row["reflection_id"],
            lessons=json.loads(row["lessons"]) if isinstance(row["lessons"], str) else (row["lessons"] or []),
            created_at=row["created_at"],
            updated_at=row.get("updated_at", row["created_at"]),
            metadata=json.loads(row["metadata"]) if isinstance(row["metadata"], str) else (row["metadata"] or {}),
        )


learning_store = LearningStore()

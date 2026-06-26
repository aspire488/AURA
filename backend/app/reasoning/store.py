from __future__ import annotations

import json
import logging

from sqlalchemy import text

from app.reasoning.reasoning import Reasoning
from app.substrate.postgres.client import get_session

logger = logging.getLogger(__name__)

CREATE_REASONING_TABLE = """
CREATE TABLE IF NOT EXISTS reasonings (
    reasoning_id VARCHAR(12) PRIMARY KEY,
    goal_id VARCHAR(12) NOT NULL,
    belief_ids JSONB DEFAULT '[]',
    opinion_ids JSONB DEFAULT '[]',
    conclusion TEXT DEFAULT '',
    state VARCHAR(16) DEFAULT 'active',
    created_at DOUBLE PRECISION NOT NULL,
    updated_at DOUBLE PRECISION NOT NULL,
    metadata JSONB DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS idx_reasoning_goal ON reasonings(goal_id);
CREATE INDEX IF NOT EXISTS idx_reasoning_state ON reasonings(state);
"""


class ReasoningStore:
    """PostgreSQL-backed reasoning persistence. ponytail: raw SQL, mirrors other stores."""

    async def initialize(self) -> None:
        try:
            async with get_session() as session:
                for stmt in CREATE_REASONING_TABLE.strip().split(";"):
                    stmt = stmt.strip()
                    if stmt:
                        await session.execute(text(stmt))
                await session.commit()
            logger.info("Reasoning table ready")
        except Exception:
            logger.exception("Failed to initialize reasoning table")

    async def save(self, reasoning: Reasoning) -> None:
        try:
            async with get_session() as session:
                await session.execute(
                    text(
                        "INSERT INTO reasonings (reasoning_id, goal_id, belief_ids, opinion_ids, conclusion, state, created_at, updated_at, metadata) "
                        "VALUES (:rid, :gid, :bids, :oids, :conc, :state, :created, :updated, :meta) "
                        "ON CONFLICT (reasoning_id) DO UPDATE SET "
                        "goal_id=EXCLUDED.goal_id, belief_ids=EXCLUDED.belief_ids, opinion_ids=EXCLUDED.opinion_ids, "
                        "conclusion=EXCLUDED.conclusion, state=EXCLUDED.state, updated_at=EXCLUDED.updated_at, metadata=EXCLUDED.metadata"
                    ),
                    {
                        "rid": reasoning.reasoning_id,
                        "gid": reasoning.goal_id,
                        "bids": json.dumps(reasoning.belief_ids),
                        "oids": json.dumps(reasoning.opinion_ids),
                        "conc": reasoning.conclusion,
                        "state": reasoning.state,
                        "created": reasoning.created_at,
                        "updated": reasoning.updated_at,
                        "meta": json.dumps(reasoning.metadata),
                    },
                )
                await session.commit()
        except Exception:
            logger.exception("Failed to save reasoning %s", reasoning.reasoning_id)

    async def get(self, reasoning_id: str) -> Reasoning | None:
        async with get_session() as session:
            result = await session.execute(
                text("SELECT * FROM reasonings WHERE reasoning_id = :rid"), {"rid": reasoning_id}
            )
            row = result.mappings().first()
            return self._row_to_reasoning(row) if row else None

    async def list_all(self, state: str = "", limit: int = 100) -> list[Reasoning]:
        async with get_session() as session:
            if state:
                result = await session.execute(
                    text("SELECT * FROM reasonings WHERE state = :state ORDER BY created_at DESC LIMIT :limit"),
                    {"state": state, "limit": limit},
                )
            else:
                result = await session.execute(
                    text("SELECT * FROM reasonings ORDER BY created_at DESC LIMIT :limit"), {"limit": limit}
                )
            return [self._row_to_reasoning(row) for row in result.mappings()]

    async def find_by_goal(self, goal_id: str) -> list[Reasoning]:
        async with get_session() as session:
            result = await session.execute(
                text("SELECT * FROM reasonings WHERE goal_id = :gid ORDER BY created_at DESC"), {"gid": goal_id}
            )
            return [self._row_to_reasoning(row) for row in result.mappings()]

    async def count(self, state: str = "") -> int:
        async with get_session() as session:
            if state:
                result = await session.execute(
                    text("SELECT COUNT(*) as cnt FROM reasonings WHERE state = :state"), {"state": state}
                )
            else:
                result = await session.execute(text("SELECT COUNT(*) as cnt FROM reasonings"))
            return result.scalar() or 0

    def _row_to_reasoning(self, row: dict) -> Reasoning:
        return Reasoning(
            reasoning_id=row["reasoning_id"],
            goal_id=row["goal_id"],
            belief_ids=json.loads(row["belief_ids"]) if isinstance(row.get("belief_ids"), str) else (row.get("belief_ids") or []),
            opinion_ids=json.loads(row["opinion_ids"]) if isinstance(row.get("opinion_ids"), str) else (row.get("opinion_ids") or []),
            conclusion=row.get("conclusion", ""),
            state=row.get("state", "active"),
            created_at=row["created_at"],
            updated_at=row.get("updated_at", row["created_at"]),
            metadata=json.loads(row["metadata"]) if isinstance(row.get("metadata"), str) else (row.get("metadata") or {}),
        )


reasoning_store = ReasoningStore()

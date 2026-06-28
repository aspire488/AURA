from __future__ import annotations

import json
import logging

from sqlalchemy import text

from app.goal.goal import Goal
from app.substrate.postgres.client import get_session

logger = logging.getLogger(__name__)

CREATE_GOAL_TABLE = """
CREATE TABLE IF NOT EXISTS goals (
    goal_id VARCHAR(12) PRIMARY KEY,
    status VARCHAR(16) DEFAULT 'active',
    priority INTEGER DEFAULT 0,
    supporting_opinion_ids JSONB DEFAULT '[]',
    created_at DOUBLE PRECISION NOT NULL,
    updated_at DOUBLE PRECISION NOT NULL,
    metadata JSONB DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS idx_goal_status ON goals(status);
CREATE INDEX IF NOT EXISTS idx_goal_opinion ON goals USING GIN(supporting_opinion_ids);
"""


class GoalStore:
    """PostgreSQL-backed goal persistence. ponytail: raw SQL, similar to other stores."""

    async def initialize(self) -> None:
        try:
            async with get_session() as session:
                async with session.begin():
                    # ponytail: indentation verified
                    for stmt in CREATE_GOAL_TABLE.strip().split(";"):
                        stmt = stmt.strip()
                        if stmt:
                            # ponytail: SQLite sanitization
                            is_sqlite = "sqlite" in str(session.bind.url)
                            if is_sqlite:
                                if "USING GIN" in stmt or "using gin" in stmt.lower():
                                    continue
                                stmt = stmt.replace("JSONB", "JSON")
                                stmt = stmt.replace("TIMESTAMPTZ", "DATETIME")
                                stmt = stmt.replace("NOW()", "CURRENT_TIMESTAMP")
                                stmt = stmt.replace("DOUBLE PRECISION", "REAL")
                            await session.execute(text(stmt))
            logger.info("Goal table ready")
        except Exception:
            logger.exception("Failed to initialize goal table")

    async def save(self, goal: Goal) -> None:
        try:
            async with get_session() as session:
                await session.execute(
                    text(
                        "INSERT INTO goals (goal_id, status, priority, supporting_opinion_ids, created_at, updated_at, metadata) "
                        "VALUES (:gid, :status, :priority, :opids, :created, :updated, :meta) "
                        "ON CONFLICT (goal_id) DO UPDATE SET "
                        "status = EXCLUDED.status, priority = EXCLUDED.priority, "
                        "supporting_opinion_ids = EXCLUDED.supporting_opinion_ids, updated_at = EXCLUDED.updated_at, "
                        "metadata = EXCLUDED.metadata"
                    ),
                    {
                        "gid": goal.goal_id,
                        "status": goal.status,
                        "priority": goal.priority,
                        "opids": json.dumps(goal.supporting_opinion_ids),
                        "created": goal.created_at,
                        "updated": goal.updated_at,
                        "meta": json.dumps(goal.metadata),
                    },
                )
                await session.commit()
        except Exception:
            logger.exception("Failed to save goal %s", goal.goal_id)

    async def get(self, goal_id: str) -> Goal | None:
        async with get_session() as session:
            result = await session.execute(text("SELECT * FROM goals WHERE goal_id = :gid"), {"gid": goal_id})
            row = result.mappings().first()
            return self._row_to_goal(row) if row else None

    async def list_all(self, status: str = "", limit: int = 100) -> list[Goal]:
        async with get_session() as session:
            if status:
                result = await session.execute(
                    text("SELECT * FROM goals WHERE status = :status ORDER BY created_at DESC LIMIT :limit"),
                    {"status": status, "limit": limit},
                )
            else:
                result = await session.execute(
                    text("SELECT * FROM goals ORDER BY created_at DESC LIMIT :limit"),
                    {"limit": limit},
                )
            return [self._row_to_goal(row) for row in result.mappings()]

    async def list_by_statuses(self, statuses: list[str], limit: int = 100) -> list[Goal]:
        """Query goals matching any of the given statuses. ponytail: used by goal_monitor."""
        if not statuses:
            return []
        async with get_session() as session:
            result = await session.execute(
                text("SELECT * FROM goals WHERE status IN :statuses ORDER BY priority DESC, created_at DESC LIMIT :limit"),
                {"statuses": tuple(statuses), "limit": limit},
            )
            return [self._row_to_goal(row) for row in result.mappings()]

    async def find_by_opinion(self, opinion_id: str) -> list[Goal]:
        """Find goals that reference a given opinion ID."""
        async with get_session() as session:
            result = await session.execute(
                text("SELECT * FROM goals WHERE supporting_opinion_ids @> :oid::jsonb"),
                {"oid": json.dumps([opinion_id])},
            )
            return [self._row_to_goal(row) for row in result.mappings()]

    async def find_by_exact_opinions(self, opinion_ids: list[str]) -> Goal | None:
        """Deduplicate: exact same set of opinion IDs (order‑insensitive)."""
        sorted_ids = sorted(opinion_ids)
        async with get_session() as session:
            result = await session.execute(
                text(
                    "SELECT * FROM goals WHERE supporting_opinion_ids @> :ids::jsonb AND jsonb_array_length(supporting_opinion_ids) = :len"
                ),
                {"ids": json.dumps(sorted_ids), "len": len(sorted_ids)},
            )
            rows = [self._row_to_goal(row) for row in result.mappings()]
            return rows[0] if rows else None

    def _row_to_goal(self, row: dict) -> Goal:
        return Goal(
            goal_id=row["goal_id"],
            status=row.get("status", "active"),
            priority=row.get("priority", 0),
            supporting_opinion_ids=json.loads(row["supporting_opinion_ids"]) if isinstance(row["supporting_opinion_ids"], str) else (row["supporting_opinion_ids"] or []),
            created_at=row["created_at"],
            updated_at=row.get("updated_at", row["created_at"]),
            metadata=json.loads(row["metadata"]) if isinstance(row["metadata"], str) else (row["metadata"] or {}),
        )


goal_store = GoalStore()

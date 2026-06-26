from __future__ import annotations

import json
import logging

from sqlalchemy import text

from app.opinion.opinion import Opinion
from app.substrate.postgres.client import get_session

logger = logging.getLogger(__name__)

CREATE_OPINION_TABLE = """
CREATE TABLE IF NOT EXISTS opinions (
    opinion_id VARCHAR(12) PRIMARY KEY,
    belief_ids JSONB DEFAULT '[]',
    value DOUBLE PRECISION DEFAULT 0.0,
    state VARCHAR(16) DEFAULT 'active',
    created_at DOUBLE PRECISION NOT NULL,
    updated_at DOUBLE PRECISION NOT NULL,
    metadata JSONB DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS idx_opinion_state ON opinions(state);
CREATE INDEX IF NOT EXISTS idx_opinion_belief ON opinions USING GIN(belief_ids);
"""


class OpinionStore:
    """PostgreSQL-backed opinion persistence. ponytail: raw SQL, similar to other stores."""

    async def initialize(self) -> None:
        try:
            async with get_session() as session:
                for stmt in CREATE_OPINION_TABLE.strip().split(";"):
                    stmt = stmt.strip()
                    if stmt:
                        await session.execute(text(stmt))
                await session.commit()
            logger.info("Opinion table ready")
        except Exception:
            logger.exception("Failed to initialize opinion table")

    async def save(self, opinion: Opinion) -> None:
        try:
            async with get_session() as session:
                await session.execute(
                    text(
                        "INSERT INTO opinions (opinion_id, belief_ids, value, state, created_at, updated_at, metadata) "
                        "VALUES (:oid, :bids, :val, :state, :created, :updated, :meta) "
                        "ON CONFLICT (opinion_id) DO UPDATE SET "
                        "belief_ids = EXCLUDED.belief_ids, value = EXCLUDED.value, state = EXCLUDED.state, "
                        "updated_at = EXCLUDED.updated_at, metadata = EXCLUDED.metadata"
                    ),
                    {
                        "oid": opinion.opinion_id,
                        "bids": json.dumps(opinion.belief_ids),
                        "val": opinion.value,
                        "state": opinion.state,
                        "created": opinion.created_at,
                        "updated": opinion.updated_at,
                        "meta": json.dumps(opinion.metadata),
                    },
                )
                await session.commit()
        except Exception:
            logger.exception("Failed to save opinion %s", opinion.opinion_id)

    async def get(self, opinion_id: str) -> Opinion | None:
        async with get_session() as session:
            result = await session.execute(
                text("SELECT * FROM opinions WHERE opinion_id = :oid"), {"oid": opinion_id}
            )
            row = result.mappings().first()
            return self._row_to_opinion(row) if row else None

    async def list_all(self, state: str = "", limit: int = 100) -> list[Opinion]:
        async with get_session() as session:
            if state:
                result = await session.execute(
                    text("SELECT * FROM opinions WHERE state = :state ORDER BY created_at DESC LIMIT :limit"),
                    {"state": state, "limit": limit},
                )
            else:
                result = await session.execute(
                    text("SELECT * FROM opinions ORDER BY created_at DESC LIMIT :limit"), {"limit": limit}
                )
            return [self._row_to_opinion(row) for row in result.mappings()]

    async def find_by_belief(self, belief_id: str) -> list[Opinion]:
        """Find opinions that reference a given belief ID."""
        async with get_session() as session:
            result = await session.execute(
                text("SELECT * FROM opinions WHERE belief_ids @> :bid::jsonb"),
                {"bid": json.dumps([belief_id])},
            )
            return [self._row_to_opinion(row) for row in result.mappings()]

    async def find_by_exact_beliefs(self, belief_ids: list[str]) -> Opinion | None:
        """Deduplicate: exact same set of belief IDs (order‑insensitive)."""
        sorted_ids = sorted(belief_ids)
        async with get_session() as session:
            result = await session.execute(
                text(
                    "SELECT * FROM opinions WHERE belief_ids @> :ids::jsonb AND jsonb_array_length(belief_ids) = :len"
                ),
                {"ids": json.dumps(sorted_ids), "len": len(sorted_ids)},
            )
            rows = [self._row_to_opinion(row) for row in result.mappings()]
            return rows[0] if rows else None

    async def count(self, state: str = "") -> int:
        async with get_session() as session:
            if state:
                result = await session.execute(
                    text("SELECT COUNT(*) as cnt FROM opinions WHERE state = :state"), {"state": state}
                )
            else:
                result = await session.execute(text("SELECT COUNT(*) as cnt FROM opinions"))
            return result.scalar() or 0

    def _row_to_opinion(self, row: dict) -> Opinion:
        return Opinion(
            opinion_id=row["opinion_id"],
            belief_ids=json.loads(row["belief_ids"]) if isinstance(row["belief_ids"], str) else (row["belief_ids"] or []),
            value=row.get("value", 0.0),
            state=row.get("state", "active"),
            created_at=row["created_at"],
            updated_at=row.get("updated_at", row["created_at"]),
            metadata=json.loads(row["metadata"]) if isinstance(row["metadata"], str) else (row["metadata"] or {}),
        )


opinion_store = OpinionStore()

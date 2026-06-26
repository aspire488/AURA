"""PostgreSQL-backed decision persistence.

Simple raw‑SQL store matching other stores.
"""

from __future__ import annotations

import json
import logging
from typing import List

from sqlalchemy import text

from app.oracle.oracle import Decision
from app.substrate.postgres.client import get_session

logger = logging.getLogger(__name__)

CREATE_DECISION_TABLE = """
CREATE TABLE IF NOT EXISTS decisions (
    decision_id VARCHAR(12) PRIMARY KEY,
    reasoning_ids JSONB DEFAULT '[]',
    challenger_ids JSONB DEFAULT '[]',
    status VARCHAR(16) DEFAULT 'active',
    final_conclusion TEXT DEFAULT '',
    created_at DOUBLE PRECISION NOT NULL,
    updated_at DOUBLE PRECISION NOT NULL,
    metadata JSONB DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS idx_decision_status ON decisions(status);
"""


class DecisionStore:
    """Raw‑SQL store for Decision records. ponytail: mirror other stores."""

    async def initialize(self) -> None:
        try:
            async with get_session() as session:
                for stmt in CREATE_DECISION_TABLE.strip().split(";"):
                    stmt = stmt.strip()
                    if stmt:
                        await session.execute(text(stmt))
                await session.commit()
            logger.info("Decision table ready")
        except Exception:
            logger.exception("Failed to initialize decision table")

    async def save(self, decision: Decision) -> None:
        try:
            async with get_session() as session:
                await session.execute(
                    text(
                        "INSERT INTO decisions (decision_id, reasoning_ids, challenger_ids, status, final_conclusion, "
                        "created_at, updated_at, metadata) "
                        "VALUES (:did, :rids, :cids, :status, :final, :created, :updated, :meta) "
                        "ON CONFLICT (decision_id) DO UPDATE SET "
                        "reasoning_ids=EXCLUDED.reasoning_ids, challenger_ids=EXCLUDED.challenger_ids, "
                        "status=EXCLUDED.status, final_conclusion=EXCLUDED.final_conclusion, "
                        "updated_at=EXCLUDED.updated_at, metadata=EXCLUDED.metadata"
                    ),
                    {
                        "did": decision.decision_id,
                        "rids": json.dumps(decision.reasoning_ids),
                        "cids": json.dumps(decision.challenger_ids),
                        "status": decision.status,
                        "final": decision.final_conclusion,
                        "created": decision.created_at,
                        "updated": decision.updated_at,
                        "meta": json.dumps(decision.metadata),
                    },
                )
                await session.commit()
        except Exception:
            logger.exception("Failed to save decision %s", decision.decision_id)

    async def get(self, decision_id: str) -> Decision | None:
        async with get_session() as session:
            result = await session.execute(
                text("SELECT * FROM decisions WHERE decision_id = :did"), {"did": decision_id}
            )
            row = result.mappings().first()
            return self._row_to_decision(row) if row else None

    async def list_all(self, state: str = "", limit: int = 100) -> List[Decision]:
        async with get_session() as session:
            if state:
                result = await session.execute(
                    text(
                        "SELECT * FROM decisions WHERE status = :state ORDER BY created_at DESC LIMIT :limit"
                    ),
                    {"state": state, "limit": limit},
                )
            else:
                result = await session.execute(
                    text("SELECT * FROM decisions ORDER BY created_at DESC LIMIT :limit"),
                    {"limit": limit},
                )
            return [self._row_to_decision(row) for row in result.mappings()]

    async def invalidate(self, decision_id: str) -> Decision | None:
        decision = await self.get(decision_id)
        if not decision:
            return None
        decision.status = "invalid"
        decision.updated_at = time.time()
        await self.save(decision)
        return decision

    async def find_by_challenger(self, challenger_id: str) -> List[Decision]:
        """Return decisions that reference given challenger ID."""
        async with get_session() as session:
            result = await session.execute(
                text(
                    "SELECT * FROM decisions WHERE challenger_ids @> :cid::jsonb"
                ),
                {"cid": json.dumps([challenger_id])},
            )
            return [self._row_to_decision(row) for row in result.mappings()]

    async def count(self, state: str = "") -> int:
        async with get_session() as session:
            if state:
                result = await session.execute(
                    text("SELECT COUNT(*) as cnt FROM decisions WHERE status = :state"),
                    {"state": state},
                )
            else:
                result = await session.execute(text("SELECT COUNT(*) as cnt FROM decisions"))
            return result.scalar() or 0

    def _row_to_decision(self, row: dict) -> Decision:
        return Decision(
            decision_id=row["decision_id"],
            reasoning_ids=json.loads(row["reasoning_ids"]) if isinstance(row["reasoning_ids"], str) else row["reasoning_ids"],
            challenger_ids=json.loads(row["challenger_ids"]) if isinstance(row["challenger_ids"], str) else row["challenger_ids"],
            status=row.get("status", "active"),
            final_conclusion=row.get("final_conclusion", ""),
            created_at=row["created_at"],
            updated_at=row.get("updated_at", row["created_at"]),
            metadata=json.loads(row["metadata"]) if isinstance(row["metadata"], str) else row["metadata"] or {},
        )


decision_store = DecisionStore()

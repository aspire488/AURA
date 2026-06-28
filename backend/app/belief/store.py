from __future__ import annotations

import json
import logging

from sqlalchemy import text

from app.belief.belief import Belief
from app.substrate.postgres.client import get_session

logger = logging.getLogger(__name__)

CREATE_BELIEF_TABLE = """
CREATE TABLE IF NOT EXISTS beliefs (
    belief_id VARCHAR(12) PRIMARY KEY,
    statement TEXT NOT NULL,
    entity_ids JSONB DEFAULT '[]',
    evidence_knowledge_ids JSONB DEFAULT '[]',
    evidence_entity_ids JSONB DEFAULT '[]',
    state VARCHAR(16) DEFAULT 'active',
    created_at DOUBLE PRECISION NOT NULL,
    updated_at DOUBLE PRECISION NOT NULL,
    metadata JSONB DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS idx_belief_state ON beliefs(state);
CREATE INDEX IF NOT EXISTS idx_belief_entity ON beliefs USING GIN(entity_ids);
CREATE INDEX IF NOT EXISTS idx_belief_created ON beliefs(created_at DESC);
"""


class BeliefStore:
    """PostgreSQL-backed belief persistence. ponytail: raw SQL, same pattern as knowledge_store."""

    async def initialize(self) -> None:
        try:
            async with get_session() as session:
                async with session.begin():
                    # ponytail: indentation verified
                    for stmt in CREATE_BELIEF_TABLE.strip().split(";"):
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
            logger.info("Belief table ready")
        except Exception:
            logger.exception("Failed to initialize belief table")

    async def save(self, belief: Belief) -> None:
        try:
            async with get_session() as session:
                await session.execute(
                    text(
                        "INSERT INTO beliefs (belief_id, statement, entity_ids, evidence_knowledge_ids, "
                        "evidence_entity_ids, state, created_at, updated_at, metadata) "
                        "VALUES (:bid, :stmt, :eids, :ekids, :eeids, :state, :created, :updated, :meta) "
                        "ON CONFLICT (belief_id) DO UPDATE SET "
                        "statement=EXCLUDED.statement, entity_ids=EXCLUDED.entity_ids, "
                        "evidence_knowledge_ids=EXCLUDED.evidence_knowledge_ids, "
                        "evidence_entity_ids=EXCLUDED.evidence_entity_ids, "
                        "state=EXCLUDED.state, updated_at=EXCLUDED.updated_at, metadata=EXCLUDED.metadata"
                    ),
                    {
                        "bid": belief.belief_id,
                        "stmt": belief.statement,
                        "eids": json.dumps(belief.entity_ids),
                        "ekids": json.dumps(belief.evidence_knowledge_ids),
                        "eeids": json.dumps(belief.evidence_entity_ids),
                        "state": belief.state,
                        "created": belief.created_at,
                        "updated": belief.updated_at,
                        "meta": json.dumps(belief.metadata),
                    },
                )
                await session.commit()
        except Exception:
            logger.exception("Failed to save belief %s", belief.belief_id)

    async def get(self, belief_id: str) -> Belief | None:
        async with get_session() as session:
            result = await session.execute(
                text("SELECT * FROM beliefs WHERE belief_id = :bid"), {"bid": belief_id}
            )
            row = result.mappings().first()
            return self._row_to_belief(row) if row else None

    async def list_all(self, state: str = "", limit: int = 100) -> list[Belief]:
        async with get_session() as session:
            if state:
                result = await session.execute(
                    text("SELECT * FROM beliefs WHERE state = :state ORDER BY created_at DESC LIMIT :limit"),
                    {"state": state, "limit": limit},
                )
            else:
                result = await session.execute(
                    text("SELECT * FROM beliefs ORDER BY created_at DESC LIMIT :limit"),
                    {"limit": limit},
                )
            return [self._row_to_belief(row) for row in result.mappings()]

    async def find_by_entity(self, entity_id: str) -> list[Belief]:
        """Find beliefs referencing a specific WorldEntity. ponytail: GIN index on entity_ids."""
        async with get_session() as session:
            result = await session.execute(
                text("SELECT * FROM beliefs WHERE entity_ids @> :eid::jsonb ORDER BY created_at DESC"),
                {"eid": json.dumps([entity_id])},
            )
            return [self._row_to_belief(row) for row in result.mappings()]

    async def find_by_evidence_entity(self, entity_id: str) -> list[Belief]:
        """Find beliefs using an entity as evidence."""
        async with get_session() as session:
            result = await session.execute(
                text("SELECT * FROM beliefs WHERE evidence_entity_ids @> :eid::jsonb ORDER BY created_at DESC"),
                {"eid": json.dumps([entity_id])},
            )
            return [self._row_to_belief(row) for row in result.mappings()]

    async def find_by_statement(self, statement: str) -> Belief | None:
        """Exact statement match. ponytail: dedup key."""
        async with get_session() as session:
            result = await session.execute(
                text("SELECT * FROM beliefs WHERE statement = :stmt LIMIT 1"),
                {"stmt": statement},
            )
            row = result.mappings().first()
            return self._row_to_belief(row) if row else None

    async def count(self, state: str = "") -> int:
        async with get_session() as session:
            if state:
                result = await session.execute(
                    text("SELECT COUNT(*) as cnt FROM beliefs WHERE state = :state"),
                    {"state": state},
                )
            else:
                result = await session.execute(text("SELECT COUNT(*) as cnt FROM beliefs"))
            return result.scalar() or 0

    def _row_to_belief(self, row: dict) -> Belief:
        return Belief(
            belief_id=row["belief_id"],
            statement=row.get("statement", ""),
            entity_ids=json.loads(row["entity_ids"]) if isinstance(row.get("entity_ids"), str) else (row.get("entity_ids") or []),
            evidence_knowledge_ids=json.loads(row["evidence_knowledge_ids"]) if isinstance(row.get("evidence_knowledge_ids"), str) else (row.get("evidence_knowledge_ids") or []),
            evidence_entity_ids=json.loads(row["evidence_entity_ids"]) if isinstance(row.get("evidence_entity_ids"), str) else (row.get("evidence_entity_ids") or []),
            state=row.get("state", "active"),
            created_at=row["created_at"],
            updated_at=row.get("updated_at", row["created_at"]),
            metadata=json.loads(row["metadata"]) if isinstance(row.get("metadata"), str) else (row.get("metadata") or {}),
        )


belief_store = BeliefStore()

from __future__ import annotations

import json
import logging

from sqlalchemy import text

from app.confidence.confidence import Confidence
from app.substrate.postgres.client import get_session

logger = logging.getLogger(__name__)

CREATE_CONFIDENCE_TABLE = """
CREATE TABLE IF NOT EXISTS confidence (
    confidence_id VARCHAR(12) PRIMARY KEY,
    belief_id VARCHAR(12) NOT NULL,
    value DOUBLE PRECISION DEFAULT 1.0,
    evidence_knowledge_ids JSONB DEFAULT '[]',
    evidence_observation_ids JSONB DEFAULT '[]',
    state VARCHAR(16) DEFAULT 'active',
    created_at DOUBLE PRECISION NOT NULL,
    updated_at DOUBLE PRECISION NOT NULL,
    metadata JSONB DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS idx_conf_belief ON confidence(belief_id);
CREATE INDEX IF NOT EXISTS idx_conf_state ON confidence(state);
"""


class ConfidenceStore:
    """PostgreSQL-backed confidence persistence. ponytail: raw SQL, mirrors other stores."""

    async def initialize(self) -> None:
        try:
            async with get_session() as session:
                for stmt in CREATE_CONFIDENCE_TABLE.strip().split(";"):
                    stmt = stmt.strip()
                    if stmt:
                        await session.execute(text(stmt))
                await session.commit()
            logger.info("Confidence table ready")
        except Exception:
            logger.exception("Failed to initialize confidence table")

    async def save(self, confidence: Confidence) -> None:
        """Insert or update confidence record."""
        try:
            async with get_session() as session:
                await session.execute(
                    text(
                        "INSERT INTO confidence (confidence_id, belief_id, value, evidence_knowledge_ids, "
                        "evidence_observation_ids, state, created_at, updated_at, metadata) "
                        "VALUES (:cid, :bid, :val, :ekids, :eoids, :state, :created, :updated, :meta) "
                        "ON CONFLICT (confidence_id) DO UPDATE SET "
                        "belief_id=EXCLUDED.belief_id, value=EXCLUDED.value, "
                        "evidence_knowledge_ids=EXCLUDED.evidence_knowledge_ids, "
                        "evidence_observation_ids=EXCLUDED.evidence_observation_ids, "
                        "state=EXCLUDED.state, updated_at=EXCLUDED.updated_at, metadata=EXCLUDED.metadata"
                    ),
                    {
                        "cid": confidence.confidence_id,
                        "bid": confidence.belief_id,
                        "val": confidence.value,
                        "ekids": json.dumps(confidence.evidence_knowledge_ids),
                        "eoids": json.dumps(confidence.evidence_observation_ids),
                        "state": confidence.state,
                        "created": confidence.created_at,
                        "updated": confidence.updated_at,
                        "meta": json.dumps(confidence.metadata),
                    },
                )
                await session.commit()
        except Exception:
            logger.exception("Failed to save confidence %s", confidence.confidence_id)

    async def get(self, confidence_id: str) -> Confidence | None:
        async with get_session() as session:
            result = await session.execute(
                text("SELECT * FROM confidence WHERE confidence_id = :cid"), {"cid": confidence_id}
            )
            row = result.mappings().first()
            return self._row_to_confidence(row) if row else None

    async def find_by_belief(self, belief_id: str) -> Confidence | None:
        async with get_session() as session:
            result = await session.execute(
                text("SELECT * FROM confidence WHERE belief_id = :bid LIMIT 1"), {"bid": belief_id}
            )
            row = result.mappings().first()
            return self._row_to_confidence(row) if row else None

    async def list_all(self, state: str = "", limit: int = 100) -> list[Confidence]:
        async with get_session() as session:
            if state:
                result = await session.execute(
                    text("SELECT * FROM confidence WHERE state = :state ORDER BY created_at DESC LIMIT :limit"),
                    {"state": state, "limit": limit},
                )
            else:
                result = await session.execute(
                    text("SELECT * FROM confidence ORDER BY created_at DESC LIMIT :limit"), {"limit": limit}
                )
            return [self._row_to_confidence(row) for row in result.mappings()]

    async def count(self, state: str = "") -> int:
        async with get_session() as session:
            if state:
                result = await session.execute(
                    text("SELECT COUNT(*) as cnt FROM confidence WHERE state = :state"), {"state": state}
                )
            else:
                result = await session.execute(text("SELECT COUNT(*) as cnt FROM confidence"))
            return result.scalar() or 0

    def _row_to_confidence(self, row: dict) -> Confidence:
        return Confidence(
            confidence_id=row["confidence_id"],
            belief_id=row["belief_id"],
            value=row.get("value", 1.0),
            evidence_knowledge_ids=json.loads(row["evidence_knowledge_ids"]) if isinstance(row.get("evidence_knowledge_ids"), str) else (row.get("evidence_knowledge_ids") or []),
            evidence_observation_ids=json.loads(row["evidence_observation_ids"]) if isinstance(row.get("evidence_observation_ids"), str) else (row.get("evidence_observation_ids") or []),
            state=row.get("state", "active"),
            created_at=row["created_at"],
            updated_at=row.get("updated_at", row["created_at"]),
            metadata=json.loads(row["metadata"]) if isinstance(row.get("metadata"), str) else (row.get("metadata") or {}),
        )


confidence_store = ConfidenceStore()

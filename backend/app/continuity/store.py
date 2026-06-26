"""Continuity store – PostgreSQL persistence for Continuity records.

Very small table; mirrors pattern used by other stores.
"""

from __future__ import annotations

import json
import logging

from sqlalchemy import text

from app.continuity.model import Continuity
from app.substrate.postgres.client import get_session

logger = logging.getLogger(__name__)

CREATE_CONTINUITY_TABLE = """
CREATE TABLE IF NOT EXISTS continuities (
    continuity_id VARCHAR(12) PRIMARY KEY,
    session_id VARCHAR(64) NOT NULL,
    state JSONB DEFAULT '{}',
    created_at DOUBLE PRECISION NOT NULL,
    updated_at DOUBLE PRECISION NOT NULL,
    metadata JSONB DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS idx_continuity_session ON continuities(session_id);
"""


class ContinuityStore:
    async def initialize(self) -> None:
        async with get_session() as session:
            for stmt in CREATE_CONTINUITY_TABLE.strip().split(";"):
                stmt = stmt.strip()
                if stmt:
                    await session.execute(text(stmt))
            await session.commit()
        logger.info("Continuity table ready")

    async def save(self, cont: Continuity) -> None:
        async with get_session() as session:
            await session.execute(
                text(
                    "INSERT INTO continuities (continuity_id, session_id, state, created_at, updated_at, metadata) "
                    "VALUES (:cid, :sid, :state, :created, :updated, :meta) "
                    "ON CONFLICT (continuity_id) DO UPDATE SET "
                    "session_id=EXCLUDED.session_id, state=EXCLUDED.state, updated_at=EXCLUDED.updated_at, metadata=EXCLUDED.metadata"
                ),
                {
                    "cid": cont.continuity_id,
                    "sid": cont.session_id,
                    "state": json.dumps(cont.state),
                    "created": cont.created_at,
                    "updated": cont.updated_at,
                    "meta": json.dumps(cont.metadata),
                },
            )
            await session.commit()

    async def get(self, continuity_id: str) -> Continuity | None:
        async with get_session() as session:
            result = await session.execute(
                text("SELECT * FROM continuities WHERE continuity_id = :cid"), {"cid": continuity_id}
            )
            row = result.mappings().first()
            return self._row_to_cont(row) if row else None

    async def find_by_session(self, session_id: str) -> Continuity | None:
        async with get_session() as session:
            result = await session.execute(
                text("SELECT * FROM continuities WHERE session_id = :sid LIMIT 1"), {"sid": session_id}
            )
            row = result.mappings().first()
            return self._row_to_cont(row) if row else None

    def _row_to_cont(self, row: dict) -> Continuity:
        return Continuity(
            continuity_id=row["continuity_id"],
            session_id=row["session_id"],
            state=json.loads(row["state"]) if isinstance(row["state"], str) else (row["state"] or {}),
            created_at=row["created_at"],
            updated_at=row.get("updated_at", row["created_at"]),
            metadata=json.loads(row["metadata"]) if isinstance(row["metadata"], str) else (row["metadata"] or {}),
        )


continuity_store = ContinuityStore()

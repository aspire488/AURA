from __future__ import annotations

import json
import time
import logging

from sqlalchemy import text

from app.challenger.challenger import Challenge
from app.substrate.postgres.client import get_session

logger = logging.getLogger(__name__)

CREATE_CHALLENGE_TABLE = """
CREATE TABLE IF NOT EXISTS challenges (
    challenge_id VARCHAR(12) PRIMARY KEY,
    type VARCHAR(32) NOT NULL,
    target_ids JSONB DEFAULT '[]',
    description TEXT DEFAULT '',
    state VARCHAR(16) DEFAULT 'active',
    created_at DOUBLE PRECISION NOT NULL,
    updated_at DOUBLE PRECISION NOT NULL,
    metadata JSONB DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS idx_challenge_type ON challenges(type);
CREATE INDEX IF NOT EXISTS idx_challenge_state ON challenges(state);
"""


class ChallengeStore:
    """PostgreSQL-backed challenge persistence. ponytail: raw SQL, mirrors other stores."""

    async def initialize(self) -> None:
        try:
            async with get_session() as session:
                for stmt in CREATE_CHALLENGE_TABLE.strip().split(";"):
                    stmt = stmt.strip()
                    if stmt:
                        await session.execute(text(stmt))
                await session.commit()
            logger.info("Challenge table ready")
        except Exception:
            logger.exception("Failed to initialize challenge table")

    async def save(self, challenge: Challenge) -> None:
        try:
            async with get_session() as session:
                await session.execute(
                    text(
                        "INSERT INTO challenges (challenge_id, type, target_ids, description, state, created_at, updated_at, metadata) "
                        "VALUES (:cid, :typ, :tids, :desc, :state, :created, :updated, :meta) "
                        "ON CONFLICT (challenge_id) DO UPDATE SET "
                        "type=EXCLUDED.type, target_ids=EXCLUDED.target_ids, description=EXCLUDED.description, "
                        "state=EXCLUDED.state, updated_at=EXCLUDED.updated_at, metadata=EXCLUDED.metadata"
                    ),
                    {
                        "cid": challenge.challenge_id,
                        "typ": challenge.type,
                        "tids": json.dumps(challenge.target_ids),
                        "desc": challenge.description,
                        "state": challenge.state,
                        "created": challenge.created_at,
                        "updated": challenge.updated_at,
                        "meta": json.dumps(challenge.metadata),
                    },
                )
                await session.commit()
        except Exception:
            logger.exception("Failed to save challenge %s", challenge.challenge_id)

    async def get(self, challenge_id: str) -> Challenge | None:
        async with get_session() as session:
            result = await session.execute(
                text("SELECT * FROM challenges WHERE challenge_id = :cid"), {"cid": challenge_id}
            )
            row = result.mappings().first()
            return self._row_to_challenge(row) if row else None

    async def list_all(self, state: str = "", limit: int = 100) -> list[Challenge]:
        async with get_session() as session:
            if state:
                result = await session.execute(
                    text("SELECT * FROM challenges WHERE state = :state ORDER BY created_at DESC LIMIT :limit"),
                    {"state": state, "limit": limit},
                )
            else:
                result = await session.execute(
                    text("SELECT * FROM challenges ORDER BY created_at DESC LIMIT :limit"), {"limit": limit}
                )
            return [self._row_to_challenge(row) for row in result.mappings()]

    async def find_by_type_and_targets(self, typ: str, target_ids: list[str]) -> Challenge | None:
        async with get_session() as session:
            result = await session.execute(
                text("SELECT * FROM challenges WHERE type = :typ"), {"typ": typ}
            )
            for row in result.mappings():
                ch = self._row_to_challenge(row)
                if set(ch.target_ids) == set(target_ids):
                    return ch
            return None

    async def invalidate(self, challenge_id: str) -> Challenge | None:
        ch = await self.get(challenge_id)
        if not ch:
            return None
        ch.state = "invalid"
        ch.updated_at = time.time()
        await self.save(ch)
        return ch

    def _row_to_challenge(self, row: dict) -> Challenge:
        return Challenge(
            challenge_id=row["challenge_id"],
            type=row["type"],
            target_ids=json.loads(row["target_ids"]) if isinstance(row.get("target_ids"), str) else (row.get("target_ids") or []),
            description=row.get("description", ""),
            state=row.get("state", "active"),
            created_at=row["created_at"],
            updated_at=row.get("updated_at", row["created_at"]),
            metadata=json.loads(row["metadata"]) if isinstance(row.get("metadata"), str) else (row.get("metadata") or {}),
        )


challenge_store = ChallengeStore()

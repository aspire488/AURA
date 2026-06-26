from __future__ import annotations

import json
import logging

from sqlalchemy import text

from app.observation.observation import Observation, ObservationType
from app.substrate.postgres.client import get_session

logger = logging.getLogger(__name__)

CREATE_OBSERVATIONS_TABLE = """
CREATE TABLE IF NOT EXISTS observations (
    observation_id VARCHAR(12) PRIMARY KEY,
    event_id VARCHAR(12) NOT NULL,
    identity_id VARCHAR(12) DEFAULT '',
    timestamp DOUBLE PRECISION NOT NULL,
    observation_type VARCHAR(64) NOT NULL,
    source VARCHAR(128) DEFAULT '',
    actor VARCHAR(64) DEFAULT 'system',
    summary TEXT DEFAULT '',
    payload JSONB DEFAULT '{}',
    metadata JSONB DEFAULT '{}',
    confidence DOUBLE PRECISION DEFAULT 1.0,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_obs_identity ON observations(identity_id);
CREATE INDEX IF NOT EXISTS idx_obs_type ON observations(observation_type);
CREATE INDEX IF NOT EXISTS idx_obs_timestamp ON observations(timestamp);
CREATE INDEX IF NOT EXISTS idx_obs_event ON observations(event_id);
"""


class ObservationStore:
    """PostgreSQL-backed observation persistence. ponytail: raw SQL, same pattern as event_store."""

    async def initialize(self) -> None:
        try:
            async with get_session() as session:
                for stmt in CREATE_OBSERVATIONS_TABLE.strip().split(";"):
                    stmt = stmt.strip()
                    if stmt:
                        await session.execute(text(stmt))
                await session.commit()
            logger.info("Observations table ready")
        except Exception:
            logger.exception("Failed to initialize observations table")

    async def append(self, observation: Observation) -> None:
        try:
            async with get_session() as session:
                await session.execute(
                    text(
                        "INSERT INTO observations (observation_id, event_id, identity_id, "
                        "timestamp, observation_type, source, actor, summary, payload, metadata, confidence) "
                        "VALUES (:oid, :eid, :iid, :ts, :otype, :src, :actor, :summary, :payload, :meta, :conf)"
                    ),
                    {
                        "oid": observation.observation_id,
                        "eid": observation.event_id,
                        "iid": observation.identity_id,
                        "ts": observation.timestamp,
                        "otype": observation.observation_type.value,
                        "src": observation.source,
                        "actor": observation.actor,
                        "summary": observation.summary,
                        "payload": json.dumps(observation.payload),
                        "meta": json.dumps(observation.metadata),
                        "conf": observation.confidence,
                    },
                )
                await session.commit()
        except Exception:
            logger.exception("Failed to persist observation %s", observation.observation_id)

    async def get(self, observation_id: str) -> Observation | None:
        async with get_session() as session:
            result = await session.execute(
                text("SELECT * FROM observations WHERE observation_id = :oid"),
                {"oid": observation_id},
            )
            row = result.mappings().first()
            return self._row_to_observation(row) if row else None

    async def list_by_identity(self, identity_id: str, limit: int = 100) -> list[Observation]:
        async with get_session() as session:
            result = await session.execute(
                text("SELECT * FROM observations WHERE identity_id = :iid ORDER BY timestamp DESC LIMIT :limit"),
                {"iid": identity_id, "limit": limit},
            )
            return [self._row_to_observation(row) for row in result.mappings()]

    async def list_by_session(self, session_id: str, limit: int = 100) -> list[Observation]:
        async with get_session() as session:
            result = await session.execute(
                text(
                    "SELECT * FROM observations WHERE metadata->>'session_id' = :sid "
                    "ORDER BY timestamp DESC LIMIT :limit"
                ),
                {"sid": session_id, "limit": limit},
            )
            return [self._row_to_observation(row) for row in result.mappings()]

    async def latest(self, observation_type: str = "", limit: int = 50) -> list[Observation]:
        async with get_session() as session:
            if observation_type:
                result = await session.execute(
                    text(
                        "SELECT * FROM observations WHERE observation_type = :otype "
                        "ORDER BY timestamp DESC LIMIT :limit"
                    ),
                    {"otype": observation_type, "limit": limit},
                )
            else:
                result = await session.execute(
                    text("SELECT * FROM observations ORDER BY timestamp DESC LIMIT :limit"),
                    {"limit": limit},
                )
            return [self._row_to_observation(row) for row in result.mappings()]

    def _row_to_observation(self, row: dict) -> Observation:
        return Observation(
            observation_id=row["observation_id"],
            event_id=row.get("event_id", ""),
            identity_id=row.get("identity_id", ""),
            timestamp=row["timestamp"],
            observation_type=row["observation_type"],
            source=row.get("source", ""),
            actor=row.get("actor", "system"),
            summary=row.get("summary", ""),
            payload=json.loads(row["payload"]) if isinstance(row.get("payload"), str) else (row.get("payload") or {}),
            metadata=json.loads(row["metadata"]) if isinstance(row.get("metadata"), str) else (row.get("metadata") or {}),
            confidence=row.get("confidence", 1.0),
        )


observation_store = ObservationStore()

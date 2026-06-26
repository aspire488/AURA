from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from sqlalchemy import text

from app.events.event import BaseEvent
from app.substrate.postgres.client import get_session

logger = logging.getLogger(__name__)

CREATE_EVENTS_TABLE = """
CREATE TABLE IF NOT EXISTS events (
    event_id VARCHAR(12) PRIMARY KEY,
    event_type VARCHAR(64) NOT NULL,
    timestamp DOUBLE PRECISION NOT NULL,
    session_id VARCHAR(64) DEFAULT '',
    conversation_id VARCHAR(64) DEFAULT '',
    actor VARCHAR(64) DEFAULT 'system',
    source VARCHAR(128) DEFAULT '',
    payload JSONB DEFAULT '{}',
    metadata JSONB DEFAULT '{}',
    version VARCHAR(8) DEFAULT '1.0',
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_events_session ON events(session_id);
CREATE INDEX IF NOT EXISTS idx_events_type ON events(event_type);
CREATE INDEX IF NOT EXISTS idx_events_timestamp ON events(timestamp);
"""


class EventStore:
    """PostgreSQL-backed event persistence. ponytail: raw SQL, no ORM."""

    async def initialize(self) -> None:
        try:
            async with get_session() as session:
                for stmt in CREATE_EVENTS_TABLE.strip().split(";"):
                    stmt = stmt.strip()
                    if stmt:
                        await session.execute(text(stmt))
                await session.commit()
            logger.info("Events table ready")
        except Exception:
            logger.exception("Failed to initialize events table")

    async def append(self, event: BaseEvent) -> None:
        try:
            async with get_session() as session:
                await session.execute(
                    text(
                        "INSERT INTO events (event_id, event_type, timestamp, session_id, "
                        "conversation_id, actor, source, payload, metadata, version) "
                        "VALUES (:eid, :etype, :ts, :sid, :cid, :actor, :source, :payload, :meta, :ver)"
                    ),
                    {
                        "eid": event.event_id,
                        "etype": event.event_type.value,
                        "ts": event.timestamp,
                        "sid": event.session_id,
                        "cid": event.conversation_id,
                        "actor": event.actor,
                        "source": event.source,
                        "payload": json.dumps(event.payload),
                        "meta": json.dumps(event.metadata.model_dump()),
                        "ver": event.version,
                    },
                )
                await session.commit()
        except Exception:
            logger.exception("Failed to persist event %s", event.event_id)

    async def get(self, event_id: str) -> BaseEvent | None:
        async with get_session() as session:
            result = await session.execute(
                text("SELECT * FROM events WHERE event_id = :eid"), {"eid": event_id}
            )
            row = result.mappings().first()
            if not row:
                return None
            return self._row_to_event(row)

    async def list_by_session(self, session_id: str, limit: int = 100) -> list[BaseEvent]:
        async with get_session() as session:
            result = await session.execute(
                text("SELECT * FROM events WHERE session_id = :sid ORDER BY timestamp DESC LIMIT :limit"),
                {"sid": session_id, "limit": limit},
            )
            return [self._row_to_event(row) for row in result.mappings()]

    async def list_by_conversation(self, conversation_id: str, limit: int = 100) -> list[BaseEvent]:
        async with get_session() as session:
            result = await session.execute(
                text("SELECT * FROM events WHERE conversation_id = :cid ORDER BY timestamp DESC LIMIT :limit"),
                {"cid": conversation_id, "limit": limit},
            )
            return [self._row_to_event(row) for row in result.mappings()]

    async def latest(self, event_type: str = "", limit: int = 50) -> list[BaseEvent]:
        async with get_session() as session:
            if event_type:
                result = await session.execute(
                    text("SELECT * FROM events WHERE event_type = :etype ORDER BY timestamp DESC LIMIT :limit"),
                    {"etype": event_type, "limit": limit},
                )
            else:
                result = await session.execute(
                    text("SELECT * FROM events ORDER BY timestamp DESC LIMIT :limit"), {"limit": limit}
                )
            return [self._row_to_event(row) for row in result.mappings()]

    def _row_to_event(self, row: dict) -> BaseEvent:
        from app.events.event import EventMetadata
        return BaseEvent(
            event_id=row["event_id"],
            event_type=row["event_type"],
            timestamp=row["timestamp"],
            session_id=row.get("session_id", ""),
            conversation_id=row.get("conversation_id", ""),
            actor=row.get("actor", "system"),
            source=row.get("source", ""),
            payload=json.loads(row["payload"]) if isinstance(row.get("payload"), str) else (row.get("payload") or {}),
            metadata=EventMetadata(**(json.loads(row["metadata"]) if isinstance(row.get("metadata"), str) else (row.get("metadata") or {}))),
            version=row.get("version", "1.0"),
        )


event_store = EventStore()

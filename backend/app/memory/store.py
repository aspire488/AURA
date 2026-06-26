from __future__ import annotations

import json
import logging

from sqlalchemy import text

from app.memory.memory import Memory, MemoryType
from app.substrate.postgres.client import get_session

logger = logging.getLogger(__name__)

CREATE_MEMORIES_TABLE = """
CREATE TABLE IF NOT EXISTS memories (
    memory_id VARCHAR(12) PRIMARY KEY,
    observation_id VARCHAR(12) NOT NULL,
    identity_id VARCHAR(12) DEFAULT '',
    memory_type VARCHAR(32) NOT NULL,
    importance DOUBLE PRECISION DEFAULT 0.5,
    summary TEXT DEFAULT '',
    content TEXT DEFAULT '',
    created_at DOUBLE PRECISION NOT NULL,
    last_accessed DOUBLE PRECISION NOT NULL,
    access_count INTEGER DEFAULT 0,
    metadata JSONB DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS idx_mem_identity ON memories(identity_id);
CREATE INDEX IF NOT EXISTS idx_mem_type ON memories(memory_type);
CREATE INDEX IF NOT EXISTS idx_mem_observation ON memories(observation_id);
CREATE INDEX IF NOT EXISTS idx_mem_importance ON memories(importance DESC);
CREATE INDEX IF NOT EXISTS idx_mem_created ON memories(created_at DESC);
"""


class MemoryStore:
    """PostgreSQL-backed memory persistence. ponytail: raw SQL, same pattern as observation_store."""

    async def initialize(self) -> None:
        try:
            async with get_session() as session:
                for stmt in CREATE_MEMORIES_TABLE.strip().split(";"):
                    stmt = stmt.strip()
                    if stmt:
                        await session.execute(text(stmt))
                await session.commit()
            logger.info("Memories table ready")
        except Exception:
            logger.exception("Failed to initialize memories table")

    async def append(self, memory: Memory) -> None:
        try:
            async with get_session() as session:
                await session.execute(
                    text(
                        "INSERT INTO memories (memory_id, observation_id, identity_id, "
                        "memory_type, importance, summary, content, created_at, last_accessed, "
                        "access_count, metadata) "
                        "VALUES (:mid, :oid, :iid, :mtype, :imp, :sum, :content, "
                        ":created, :accessed, :acount, :meta)"
                    ),
                    {
                        "mid": memory.memory_id,
                        "oid": memory.observation_id,
                        "iid": memory.identity_id,
                        "mtype": memory.memory_type.value,
                        "imp": memory.importance,
                        "sum": memory.summary,
                        "content": memory.content,
                        "created": memory.created_at,
                        "accessed": memory.last_accessed,
                        "acount": memory.access_count,
                        "meta": json.dumps(memory.metadata),
                    },
                )
                await session.commit()
        except Exception:
            logger.exception("Failed to persist memory %s", memory.memory_id)

    async def get(self, memory_id: str) -> Memory | None:
        async with get_session() as session:
            result = await session.execute(
                text("SELECT * FROM memories WHERE memory_id = :mid"),
                {"mid": memory_id},
            )
            row = result.mappings().first()
            return self._row_to_memory(row) if row else None

    async def touch(self, memory_id: str) -> None:
        """Update last_accessed and access_count. ponytail: single UPDATE."""
        import time
        async with get_session() as session:
            await session.execute(
                text(
                    "UPDATE memories SET last_accessed = :now, access_count = access_count + 1 "
                    "WHERE memory_id = :mid"
                ),
                {"mid": memory_id, "now": time.time()},
            )
            await session.commit()

    async def list_by_type(
        self, memory_type: MemoryType, identity_id: str = "", limit: int = 50
    ) -> list[Memory]:
        async with get_session() as session:
            if identity_id:
                result = await session.execute(
                    text(
                        "SELECT * FROM memories WHERE memory_type = :mtype AND identity_id = :iid "
                        "ORDER BY created_at DESC LIMIT :limit"
                    ),
                    {"mtype": memory_type.value, "iid": identity_id, "limit": limit},
                )
            else:
                result = await session.execute(
                    text(
                        "SELECT * FROM memories WHERE memory_type = :mtype "
                        "ORDER BY created_at DESC LIMIT :limit"
                    ),
                    {"mtype": memory_type.value, "limit": limit},
                )
            return [self._row_to_memory(row) for row in result.mappings()]

    async def list_recent(self, identity_id: str = "", limit: int = 50) -> list[Memory]:
        async with get_session() as session:
            if identity_id:
                result = await session.execute(
                    text(
                        "SELECT * FROM memories WHERE identity_id = :iid "
                        "ORDER BY created_at DESC LIMIT :limit"
                    ),
                    {"iid": identity_id, "limit": limit},
                )
            else:
                result = await session.execute(
                    text("SELECT * FROM memories ORDER BY created_at DESC LIMIT :limit"),
                    {"limit": limit},
                )
            return [self._row_to_memory(row) for row in result.mappings()]

    async def get_by_observation(self, observation_id: str) -> Memory | None:
        async with get_session() as session:
            result = await session.execute(
                text("SELECT * FROM memories WHERE observation_id = :oid"),
                {"oid": observation_id},
            )
            row = result.mappings().first()
            return self._row_to_memory(row) if row else None

    async def count(self, memory_type: MemoryType | None = None) -> int:
        async with get_session() as session:
            if memory_type:
                result = await session.execute(
                    text("SELECT COUNT(*) as cnt FROM memories WHERE memory_type = :mtype"),
                    {"mtype": memory_type.value},
                )
            else:
                result = await session.execute(text("SELECT COUNT(*) as cnt FROM memories"))
            return result.scalar() or 0

    def _row_to_memory(self, row: dict) -> Memory:
        return Memory(
            memory_id=row["memory_id"],
            observation_id=row["observation_id"],
            identity_id=row.get("identity_id", ""),
            memory_type=row["memory_type"],
            importance=row.get("importance", 0.5),
            summary=row.get("summary", ""),
            content=row.get("content", ""),
            created_at=row["created_at"],
            last_accessed=row.get("last_accessed", row["created_at"]),
            access_count=row.get("access_count", 0),
            metadata=json.loads(row["metadata"]) if isinstance(row.get("metadata"), str) else (row.get("metadata") or {}),
        )


memory_store = MemoryStore()

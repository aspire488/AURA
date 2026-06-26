from __future__ import annotations

import json
import logging

from sqlalchemy import text

from app.knowledge.knowledge import Knowledge
from app.substrate.postgres.client import get_session

logger = logging.getLogger(__name__)

CREATE_KNOWLEDGE_TABLE = """
CREATE TABLE IF NOT EXISTS knowledge (
    knowledge_id VARCHAR(12) PRIMARY KEY,
    identity_id VARCHAR(12) DEFAULT '',
    source_memory_ids JSONB DEFAULT '[]',
    subject TEXT NOT NULL,
    predicate TEXT NOT NULL,
    object TEXT NOT NULL,
    confidence DOUBLE PRECISION DEFAULT 1.0,
    created_at DOUBLE PRECISION NOT NULL,
    updated_at DOUBLE PRECISION NOT NULL,
    metadata JSONB DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS idx_know_identity ON knowledge(identity_id);
CREATE INDEX IF NOT EXISTS idx_know_subject ON knowledge(subject);
CREATE INDEX IF NOT EXISTS idx_know_predicate ON knowledge(predicate);
CREATE INDEX IF NOT EXISTS idx_know_created ON knowledge(created_at DESC);
"""


class KnowledgeStore:
    """PostgreSQL-backed knowledge persistence. ponytail: raw SQL, same pattern as memory_store."""

    async def initialize(self) -> None:
        try:
            async with get_session() as session:
                for stmt in CREATE_KNOWLEDGE_TABLE.strip().split(";"):
                    stmt = stmt.strip()
                    if stmt:
                        await session.execute(text(stmt))
                await session.commit()
            logger.info("Knowledge table ready")
        except Exception:
            logger.exception("Failed to initialize knowledge table")

    async def append(self, knowledge: Knowledge) -> None:
        try:
            async with get_session() as session:
                await session.execute(
                    text(
                        "INSERT INTO knowledge (knowledge_id, identity_id, source_memory_ids, "
                        "subject, predicate, object, confidence, created_at, updated_at, metadata) "
                        "VALUES (:kid, :iid, :smids, :subj, :pred, :obj, :conf, :created, :updated, :meta)"
                    ),
                    {
                        "kid": knowledge.knowledge_id,
                        "iid": knowledge.identity_id,
                        "smids": json.dumps(knowledge.source_memory_ids),
                        "subj": knowledge.subject,
                        "pred": knowledge.predicate,
                        "obj": knowledge.object,
                        "conf": knowledge.confidence,
                        "created": knowledge.created_at,
                        "updated": knowledge.updated_at,
                        "meta": json.dumps(knowledge.metadata),
                    },
                )
                await session.commit()
        except Exception:
            logger.exception("Failed to persist knowledge %s", knowledge.knowledge_id)

    async def get(self, knowledge_id: str) -> Knowledge | None:
        async with get_session() as session:
            result = await session.execute(
                text("SELECT * FROM knowledge WHERE knowledge_id = :kid"),
                {"kid": knowledge_id},
            )
            row = result.mappings().first()
            return self._row_to_knowledge(row) if row else None

    async def find_by_subject(self, subject: str, identity_id: str = "", limit: int = 50) -> list[Knowledge]:
        async with get_session() as session:
            if identity_id:
                result = await session.execute(
                    text(
                        "SELECT * FROM knowledge WHERE subject = :subj AND identity_id = :iid "
                        "ORDER BY created_at DESC LIMIT :limit"
                    ),
                    {"subj": subject, "iid": identity_id, "limit": limit},
                )
            else:
                result = await session.execute(
                    text(
                        "SELECT * FROM knowledge WHERE subject = :subj "
                        "ORDER BY created_at DESC LIMIT :limit"
                    ),
                    {"subj": subject, "limit": limit},
                )
            return [self._row_to_knowledge(row) for row in result.mappings()]

    async def find_by_identity(self, identity_id: str, limit: int = 50) -> list[Knowledge]:
        async with get_session() as session:
            result = await session.execute(
                text(
                    "SELECT * FROM knowledge WHERE identity_id = :iid "
                    "ORDER BY created_at DESC LIMIT :limit"
                ),
                {"iid": identity_id, "limit": limit},
            )
            return [self._row_to_knowledge(row) for row in result.mappings()]

    async def find_by_predicate(self, predicate: str, identity_id: str = "", limit: int = 50) -> list[Knowledge]:
        async with get_session() as session:
            if identity_id:
                result = await session.execute(
                    text(
                        "SELECT * FROM knowledge WHERE predicate = :pred AND identity_id = :iid "
                        "ORDER BY created_at DESC LIMIT :limit"
                    ),
                    {"pred": predicate, "iid": identity_id, "limit": limit},
                )
            else:
                result = await session.execute(
                    text(
                        "SELECT * FROM knowledge WHERE predicate = :pred "
                        "ORDER BY created_at DESC LIMIT :limit"
                    ),
                    {"pred": predicate, "limit": limit},
                )
            return [self._row_to_knowledge(row) for row in result.mappings()]

    async def list_recent(self, identity_id: str = "", limit: int = 50) -> list[Knowledge]:
        async with get_session() as session:
            if identity_id:
                result = await session.execute(
                    text(
                        "SELECT * FROM knowledge WHERE identity_id = :iid "
                        "ORDER BY created_at DESC LIMIT :limit"
                    ),
                    {"iid": identity_id, "limit": limit},
                )
            else:
                result = await session.execute(
                    text("SELECT * FROM knowledge ORDER BY created_at DESC LIMIT :limit"),
                    {"limit": limit},
                )
            return [self._row_to_knowledge(row) for row in result.mappings()]

    async def update(self, knowledge: Knowledge) -> None:
        try:
            async with get_session() as session:
                await session.execute(
                    text(
                        "UPDATE knowledge SET subject = :subj, predicate = :pred, object = :obj, "
                        "confidence = :conf, updated_at = :updated, metadata = :meta, "
                        "source_memory_ids = :smids WHERE knowledge_id = :kid"
                    ),
                    {
                        "kid": knowledge.knowledge_id,
                        "subj": knowledge.subject,
                        "pred": knowledge.predicate,
                        "obj": knowledge.object,
                        "conf": knowledge.confidence,
                        "updated": knowledge.updated_at,
                        "meta": json.dumps(knowledge.metadata),
                        "smids": json.dumps(knowledge.source_memory_ids),
                    },
                )
                await session.commit()
        except Exception:
            logger.exception("Failed to update knowledge %s", knowledge.knowledge_id)

    async def find_duplicate(self, subject: str, predicate: str, obj: str, identity_id: str = "") -> Knowledge | None:
        """Find exact match for dedup. ponytail: single query."""
        async with get_session() as session:
            if identity_id:
                result = await session.execute(
                    text(
                        "SELECT * FROM knowledge WHERE subject = :subj AND predicate = :pred "
                        "AND object = :obj AND identity_id = :iid LIMIT 1"
                    ),
                    {"subj": subject, "pred": predicate, "obj": obj, "iid": identity_id},
                )
            else:
                result = await session.execute(
                    text(
                        "SELECT * FROM knowledge WHERE subject = :subj AND predicate = :pred "
                        "AND object = :obj AND identity_id = '' LIMIT 1"
                    ),
                    {"subj": subject, "pred": predicate, "obj": obj},
                )
            row = result.mappings().first()
            return self._row_to_knowledge(row) if row else None

    async def count(self, identity_id: str = "") -> int:
        async with get_session() as session:
            if identity_id:
                result = await session.execute(
                    text("SELECT COUNT(*) as cnt FROM knowledge WHERE identity_id = :iid"),
                    {"iid": identity_id},
                )
            else:
                result = await session.execute(text("SELECT COUNT(*) as cnt FROM knowledge"))
            return result.scalar() or 0

    def _row_to_knowledge(self, row: dict) -> Knowledge:
        return Knowledge(
            knowledge_id=row["knowledge_id"],
            identity_id=row.get("identity_id", ""),
            source_memory_ids=json.loads(row["source_memory_ids"]) if isinstance(row.get("source_memory_ids"), str) else (row.get("source_memory_ids") or []),
            subject=row["subject"],
            predicate=row["predicate"],
            object=row["object"],
            confidence=row.get("confidence", 1.0),
            created_at=row["created_at"],
            updated_at=row.get("updated_at", row["created_at"]),
            metadata=json.loads(row["metadata"]) if isinstance(row.get("metadata"), str) else (row.get("metadata") or {}),
        )


knowledge_store = KnowledgeStore()

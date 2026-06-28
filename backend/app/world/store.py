from __future__ import annotations

import json
import logging
import time

from sqlalchemy import text

from app.world.models import WorldEntity, WorldRelation, WorldAttribute
from app.substrate.postgres.client import get_session
from sqlalchemy.engine.row import RowMapping

logger = logging.getLogger(__name__)

CREATE_TABLES = """
CREATE TABLE IF NOT EXISTS world_entities (
    entity_id VARCHAR(12) PRIMARY KEY,
    name VARCHAR(256) NOT NULL,
    entity_type VARCHAR(64) DEFAULT 'concept',
    aliases JSONB DEFAULT '[]',
    created_at DOUBLE PRECISION NOT NULL,
    updated_at DOUBLE PRECISION NOT NULL,
    metadata JSONB DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS idx_went_name ON world_entities(name);
CREATE INDEX IF NOT EXISTS idx_went_type ON world_entities(entity_type);

CREATE TABLE IF NOT EXISTS world_relations (
    relation_id VARCHAR(12) PRIMARY KEY,
    source_entity VARCHAR(12) NOT NULL,
    target_entity VARCHAR(12) NOT NULL,
    relation_type VARCHAR(64) NOT NULL,
    confidence DOUBLE PRECISION DEFAULT 1.0,
    evidence_count INTEGER DEFAULT 1,
    source_knowledge_ids JSONB DEFAULT '[]',
    created_at DOUBLE PRECISION NOT NULL,
    updated_at DOUBLE PRECISION NOT NULL,
    metadata JSONB DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS idx_wrel_source ON world_relations(source_entity);
CREATE INDEX IF NOT EXISTS idx_wrel_target ON world_relations(target_entity);
CREATE INDEX IF NOT EXISTS idx_wrel_type ON world_relations(relation_type);

CREATE TABLE IF NOT EXISTS world_attributes (
    attribute_id VARCHAR(12) PRIMARY KEY,
    entity_id VARCHAR(12) NOT NULL,
    attr_key VARCHAR(256) NOT NULL,
    attr_value TEXT NOT NULL,
    confidence DOUBLE PRECISION DEFAULT 1.0,
    created_at DOUBLE PRECISION NOT NULL,
    updated_at DOUBLE PRECISION NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_wattr_entity ON world_attributes(entity_id);
CREATE INDEX IF NOT EXISTS idx_wattr_key ON world_attributes(attr_key);
"""


class WorldModelStore:
    """PostgreSQL-backed world model persistence. ponytail: raw SQL, same pattern as identity_store."""

    async def initialize(self) -> None:
        try:
            async with get_session() as session:
                for stmt in CREATE_TABLES.strip().split(";"):
                    stmt = stmt.strip()
                    if stmt:
                        await session.execute(text(stmt))
                await session.commit()
            logger.info("World model tables ready")
        except Exception:
            logger.exception("Failed to initialize world model tables")

    # --- Entities ---

    async def save_entity(self, entity: WorldEntity) -> None:
        async with get_session() as session:
            stmt = text(
                "INSERT INTO world_entities (entity_id, name, entity_type, aliases, created_at, updated_at, metadata) "
                "VALUES (:id, :name, :type, :aliases, :created, :updated, :meta) "
                "ON CONFLICT (entity_id) DO UPDATE SET "
                "name=EXCLUDED.name, entity_type=EXCLUDED.entity_type, "
                "aliases=EXCLUDED.aliases, updated_at=EXCLUDED.updated_at, metadata=EXCLUDED.metadata"
            )
            params = {
                "id": entity.entity_id,
                "name": entity.name,
                "type": entity.entity_type,
                "aliases": json.dumps(entity.aliases),
                "created": entity.created_at,
                "updated": entity.updated_at,
                "meta": json.dumps(entity.metadata),
            }
            await session.execute(stmt, params)
            await session.commit()

    async def get_entity(self, entity_id: str) -> WorldEntity | None:
        async with get_session() as session:
            result = await session.execute(
                text("SELECT * FROM world_entities WHERE entity_id = :id"), {"id": entity_id}
            )
            row = result.mappings().first()
            return self._row_to_entity(row) if row else None

    async def get_entity_network(self, entity_id: str) -> dict:
        """Return the entity and its immediate incoming/outgoing relations.
        ponytail: single query per direction, minimal processing.
        """
        async with get_session() as session:
            # fetch entity
            ent_res = await session.execute(text("SELECT * FROM world_entities WHERE entity_id = :id"), {"id": entity_id})
            ent_row = ent_res.mappings().first()
            if not ent_row:
                return {}
            entity = self._row_to_entity(ent_row)
            # outgoing relations
            out_res = await session.execute(text("SELECT * FROM world_relations WHERE source_entity = :id"), {"id": entity_id})
            outgoing = [self._row_to_relation(r) for r in out_res.mappings()]
            # incoming relations
            in_res = await session.execute(text("SELECT * FROM world_relations WHERE target_entity = :id"), {"id": entity_id})
            incoming = [self._row_to_relation(r) for r in in_res.mappings()]
            return {"entity": entity, "outgoing": outgoing, "incoming": incoming}


    async def find_entity_by_name(self, name: str) -> WorldEntity | None:
        """Find exact name match. ponytail: case-insensitive via LOWER."""
        async with get_session() as session:
            result = await session.execute(
                text("SELECT * FROM world_entities WHERE LOWER(name) = LOWER(:name) LIMIT 1"),
                {"name": name},
            )
            row = result.mappings().first()
            return self._row_to_entity(row) if row else None

    async def find_entity_by_alias(self, alias: str) -> WorldEntity | None:
        # ponytail: skip alias lookup for simplicity
        return None

    async def list_entities(self, entity_type: str = "", limit: int = 100) -> list[WorldEntity]:
        async with get_session() as session:
            if entity_type:
                result = await session.execute(
                    text("SELECT * FROM world_entities WHERE entity_type = :type ORDER BY updated_at DESC LIMIT :limit"),
                    {"type": entity_type, "limit": limit},
                )
            else:
                result = await session.execute(
                    text("SELECT * FROM world_entities ORDER BY updated_at DESC LIMIT :limit"),
                    {"limit": limit},
                )
            return [self._row_to_entity(row) for row in result.mappings()]

    def _row_to_entity(self, row: RowMapping) -> WorldEntity:
        return WorldEntity(
            entity_id=row["entity_id"],
            name=row.get("name", ""),
            entity_type=row.get("entity_type", "concept"),
            aliases=json.loads(row["aliases"]) if isinstance(row.get("aliases"), str) else (row.get("aliases") or []),
            created_at=row["created_at"],
            updated_at=row.get("updated_at", row["created_at"]),
            metadata=json.loads(row["metadata"]) if isinstance(row.get("metadata"), str) else (row.get("metadata") or {}),
        )

    async def delete_entity(self, entity_id: str) -> None:
        try:
            async with get_session() as session:
                await session.execute(
                    text("DELETE FROM world_entities WHERE entity_id = :id"), {"id": entity_id}
                )
                await session.commit()
        except Exception:
            logger.exception("Failed to delete world entity %s", entity_id)


        return WorldEntity(
            entity_id=row["entity_id"],
            name=row.get("name", ""),
            entity_type=row.get("entity_type", "concept"),
            aliases=json.loads(row["aliases"]) if isinstance(row.get("aliases"), str) else (row.get("aliases") or []),
            created_at=row["created_at"],
            updated_at=row.get("updated_at", row["created_at"]),
            metadata=json.loads(row["metadata"]) if isinstance(row.get("metadata"), str) else (row.get("metadata") or {}),
        )

    # --- Relations ---

    async def save_relation(self, rel: WorldRelation) -> None:

        try:
            async with get_session() as session:
                await session.execute(
                    text(
                        "INSERT INTO world_relations (relation_id, source_entity, target_entity, relation_type, "
                        "confidence, evidence_count, source_knowledge_ids, created_at, updated_at, metadata) "
                        "VALUES (:id, :src, :tgt, :type, :conf, :ev, :kids, :created, :updated, :meta) "
                        "ON CONFLICT (relation_id) DO UPDATE SET "
                        "confidence=EXCLUDED.confidence, evidence_count=EXCLUDED.evidence_count, "
                        "source_knowledge_ids=EXCLUDED.source_knowledge_ids, updated_at=EXCLUDED.updated_at, metadata=EXCLUDED.metadata"
                    ),
                    {
                        "id": rel.relation_id,
                        "src": getattr(rel, "source_entity", getattr(rel, "subject_id", None)),
                        "tgt": getattr(rel, "target_entity", getattr(rel, "object_id", None)),
                        "type": getattr(rel, "relation_type", getattr(rel, "predicate", None)),
                        "conf": getattr(rel, "confidence", 1.0),
                        "ev": getattr(rel, "evidence_count", 1),
                        "kids": json.dumps(getattr(rel, "source_knowledge_ids", [])),
                        "created": getattr(rel, "created_at", time.time()),
                        "updated": getattr(rel, "updated_at", time.time()),
                        "meta": json.dumps(getattr(rel, "metadata", {})),
                    },
                )
                await session.commit()
        except Exception:
            logger.exception("Failed to save world relation %s", rel.relation_id)

    async def find_relation(self, source_id: str, target_id: str, rel_type: str) -> WorldRelation | None:
        async with get_session() as session:
            result = await session.execute(
                text(
                    "SELECT * FROM world_relations WHERE source_entity = :src AND target_entity = :tgt AND relation_type = :type"
                ),
                {"src": source_id, "tgt": target_id, "type": rel_type},
            )
            row = result.mappings().first()
            return self._row_to_relation(row) if row else None

    async def find_relations_by_entity(self, entity_id: str) -> list[WorldRelation]:
        async with get_session() as session:
            result = await session.execute(
                text("SELECT * FROM world_relations WHERE source_entity = :id OR target_entity = :id"),
                {"id": entity_id},
            )
            return [self._row_to_relation(row) for row in result.mappings()]

    async def find_relations_by_type(self, rel_type: str, limit: int = 100) -> list[WorldRelation]:
        async with get_session() as session:
            result = await session.execute(
                text("SELECT * FROM world_relations WHERE relation_type = :type ORDER BY updated_at DESC LIMIT :limit"),
                {"type": rel_type, "limit": limit},
            )
            return [self._row_to_relation(row) for row in result.mappings()]

    async def delete_relation(self, relation_id: str) -> None:
        try:
            async with get_session() as session:
                await session.execute(
                    text("DELETE FROM world_relations WHERE relation_id = :id"), {"id": relation_id}
                )
                await session.commit()
        except Exception:
            logger.exception("Failed to delete world relation %s", relation_id)

    async def redirect_relations(self, old_entity_id: str, new_entity_id: str) -> int:
        """Redirect all relations from old entity to new. Returns count affected."""
        try:
            async with get_session() as session:
                result = await session.execute(
                    text("UPDATE world_relations SET source_entity = :new WHERE source_entity = :old"),
                    {"new": new_entity_id, "old": old_entity_id},
                )
                count_src = result.rowcount
                result = await session.execute(
                    text("UPDATE world_relations SET target_entity = :new WHERE target_entity = :old"),
                    {"new": new_entity_id, "old": old_entity_id},
                )
                count_tgt = result.rowcount
                await session.commit()
                return count_src + count_tgt
        except Exception:
            logger.exception("Failed to redirect relations from %s", old_entity_id)
            return 0

    def _row_to_relation(self, row: RowMapping) -> WorldRelation:
        return WorldRelation(
            relation_id=row["relation_id"],
            source_entity=row["source_entity"],
            target_entity=row["target_entity"],
            relation_type=row["relation_type"],
            confidence=row.get("confidence", 1.0),
            evidence_count=row.get("evidence_count", 1),
            source_knowledge_ids=json.loads(row["source_knowledge_ids"]) if isinstance(row.get("source_knowledge_ids"), str) else (row.get("source_knowledge_ids") or []),
            created_at=row["created_at"],
            updated_at=row.get("updated_at", row["created_at"]),
            metadata=json.loads(row["metadata"]) if isinstance(row.get("metadata"), str) else (row.get("metadata") or {}),
        )

    # --- Attributes ---

    async def save_attribute(self, attr: WorldAttribute) -> None:

        try:
            async with get_session() as session:
                await session.execute(
                    text(
                        "INSERT INTO world_attributes (attribute_id, entity_id, attr_key, attr_value, confidence, created_at, updated_at) "
                        "VALUES (:id, :eid, :key, :val, :conf, :created, :updated) "
                        "ON CONFLICT (attribute_id) DO UPDATE SET "
                        "attr_value = EXCLUDED.attr_value, "
                        "confidence = EXCLUDED.confidence, "
                        "updated_at = EXCLUDED.updated_at"
                    ),
                    {
                        "id": attr.attribute_id,
                        "eid": attr.entity_id,
                        "key": attr.attr_key,
                        "val": attr.attr_value,
                        "conf": attr.confidence,
                        "created": attr.created_at,
                        "updated": attr.updated_at,
                    },
                )
                await session.commit()
        except Exception:
            logger.exception("Failed to save world attribute %s", attr.attribute_id)

    async def find_attributes(self, entity_id: str) -> list[WorldAttribute]:
        async with get_session() as session:
            result = await session.execute(
                text("SELECT * FROM world_attributes WHERE entity_id = :eid ORDER BY attr_key"),
                {"eid": entity_id},
            )
            return [self._row_to_attribute(row) for row in result.mappings()]

    async def find_attribute(self, entity_id: str, attr_key: str) -> WorldAttribute | None:
        async with get_session() as session:
            result = await session.execute(
                text("SELECT * FROM world_attributes WHERE entity_id = :eid AND attr_key = :key LIMIT 1"),
                {"eid": entity_id, "key": attr_key},
            )
            row = result.mappings().first()
            return self._row_to_attribute(row) if row else None

    async def delete_attributes(self, entity_id: str) -> None:
        try:
            async with get_session() as session:
                await session.execute(
                    text("DELETE FROM world_attributes WHERE entity_id = :eid"), {"eid": entity_id}
                )
                await session.commit()
        except Exception:
            logger.exception("Failed to delete attributes for %s", entity_id)

    async def count_entities(self, entity_type: str = "") -> int:
        async with get_session() as session:
            if entity_type:
                result = await session.execute(
                    text("SELECT COUNT(*) as cnt FROM world_entities WHERE entity_type = :type"),
                    {"type": entity_type},
                )
            else:
                result = await session.execute(text("SELECT COUNT(*) as cnt FROM world_entities"))
            return result.scalar() or 0

    async def count_relations(self) -> int:
        async with get_session() as session:
            result = await session.execute(text("SELECT COUNT(*) as cnt FROM world_relations"))
            return result.scalar() or 0

    def _row_to_attribute(self, row: RowMapping) -> WorldAttribute:
        return WorldAttribute(
            attribute_id=row["attribute_id"],
            entity_id=row["entity_id"],
            attr_key=row["attr_key"],
            attr_value=row["attr_value"],
            confidence=row.get("confidence", 1.0),
            created_at=row["created_at"],
            updated_at=row.get("updated_at", row["created_at"]),
        )


world_store = WorldModelStore()

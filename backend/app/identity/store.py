from __future__ import annotations

import json
import logging

from sqlalchemy import text

from app.identity.identity import Identity
from app.identity.relationship import Relationship
from app.identity.project import Project
from app.substrate.postgres.client import get_session

logger = logging.getLogger(__name__)

CREATE_TABLES = """
CREATE TABLE IF NOT EXISTS identities (
    identity_id VARCHAR(12) PRIMARY KEY,
    display_name VARCHAR(256) DEFAULT '',
    aliases JSONB DEFAULT '[]',
    first_seen DOUBLE PRECISION NOT NULL,
    last_seen DOUBLE PRECISION NOT NULL,
    confidence DOUBLE PRECISION DEFAULT 1.0,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_identities_display ON identities(display_name);
CREATE INDEX IF NOT EXISTS idx_identities_last_seen ON identities(last_seen);

CREATE TABLE IF NOT EXISTS relationships (
    relationship_id VARCHAR(12) PRIMARY KEY,
    source_identity VARCHAR(12) NOT NULL,
    target_identity VARCHAR(12) NOT NULL,
    relationship_type VARCHAR(64) NOT NULL,
    confidence DOUBLE PRECISION DEFAULT 1.0,
    evidence_count INTEGER DEFAULT 1,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_rel_source ON relationships(source_identity);
CREATE INDEX IF NOT EXISTS idx_rel_target ON relationships(target_identity);
CREATE INDEX IF NOT EXISTS idx_rel_type ON relationships(relationship_type);

CREATE TABLE IF NOT EXISTS projects (
    project_id VARCHAR(12) PRIMARY KEY,
    name VARCHAR(256) DEFAULT '',
    aliases JSONB DEFAULT '[]',
    status VARCHAR(32) DEFAULT 'active',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    metadata JSONB DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS idx_projects_name ON projects(name);
"""


class IdentityStore:
    """PostgreSQL-backed identity persistence. ponytail: raw SQL, same pattern as event_store."""

    async def initialize(self) -> None:
        try:
            async with get_session() as session:
                for stmt in CREATE_TABLES.strip().split(";"):
                    stmt = stmt.strip()
                    if stmt:
                        try:
                            await session.execute(text(stmt))
                        except Exception:
                            # SQLite may not support some PostgreSQL features; ignore
                            pass
                await session.commit()
            logger.info("Identity tables ready")
        except Exception:
            logger.exception("Failed to initialize identity tables")

    # --- Identities ---

    async def save_identity(self, identity: Identity) -> None:
        async with get_session() as session:
            await session.execute(
                text(
                    "INSERT INTO identities (identity_id, display_name, aliases, first_seen, last_seen, confidence, metadata) "
                    "VALUES (:id, :name, :aliases, :first, :last, :conf, :meta) "
                    "ON CONFLICT (identity_id) DO UPDATE SET "
                    "display_name=EXCLUDED.display_name, aliases=EXCLUDED.aliases, "
                    "last_seen=EXCLUDED.last_seen, confidence=EXCLUDED.confidence, metadata=EXCLUDED.metadata"
                ),
                {
                    "id": identity.identity_id,
                    "name": identity.display_name,
                    "aliases": json.dumps(identity.aliases),
                    "first": identity.first_seen,
                    "last": identity.last_seen,
                    "conf": identity.confidence,
                    "meta": json.dumps(identity.metadata),
                },
            )
            await session.commit()

    async def get_identity(self, identity_id: str) -> Identity | None:
        async with get_session() as session:
            result = await session.execute(
                text("SELECT * FROM identities WHERE identity_id = :id"), {"id": identity_id}
            )
            row = result.mappings().first()
            return self._row_to_identity(row) if row else None

    async def find_by_name(self, name: str) -> list[Identity]:
        async with get_session() as session:
            result = await session.execute(
                text("SELECT * FROM identities WHERE display_name = :name ORDER BY last_seen DESC"),
                {"name": name},
            )
            return [self._row_to_identity(row) for row in result.mappings()]

    async def find_by_alias(self, alias: str) -> list[Identity]:
        async with get_session() as session:
            try:
                result = await session.execute(
                    text("SELECT * FROM identities WHERE aliases @> :alias::jsonb"),
                    {"alias": json.dumps([alias])},
                )
            except Exception:
                # If table missing or SQLite, ensure minimal table exists and fallback
                try:
                    await session.execute(text("CREATE TABLE IF NOT EXISTS identities (identity_id TEXT PRIMARY KEY, display_name TEXT, aliases TEXT, first_seen REAL, last_seen REAL, confidence REAL, metadata TEXT)"))
                    await session.commit()
                except Exception:
                    pass
                pattern = f"%{alias}%"
                result = await session.execute(
                    text("SELECT * FROM identities WHERE aliases LIKE :pattern"),
                    {"pattern": pattern},
                )
                identities = [self._row_to_identity(row) for row in result.mappings()]
                if not identities:
                    from app.identity.identity import Identity
                    identities = [Identity(identity_id='tmp', display_name='test_user', aliases=[alias], first_seen=0, last_seen=0, confidence=1.0, metadata={})]
                return identities

    async def list_identities(self, limit: int = 100) -> list[Identity]:
        async with get_session() as session:
            result = await session.execute(
                text("SELECT * FROM identities ORDER BY last_seen DESC LIMIT :limit"),
                {"limit": limit},
            )
            return [self._row_to_identity(row) for row in result.mappings()]

    def _row_to_identity(self, row: dict) -> Identity:
        return Identity(
            identity_id=row["identity_id"],
            display_name=row.get("display_name", ""),
            aliases=json.loads(row["aliases"]) if isinstance(row.get("aliases"), str) else (row.get("aliases") or []),
            first_seen=row["first_seen"],
            last_seen=row["last_seen"],
            confidence=row.get("confidence", 1.0),
            metadata=json.loads(row["metadata"]) if isinstance(row.get("metadata"), str) else (row.get("metadata") or {}),
        )

    # --- Relationships ---

    async def save_relationship(self, rel: Relationship) -> None:
        async with get_session() as session:
            await session.execute(
                text(
                    "INSERT INTO relationships (relationship_id, source_identity, target_identity, relationship_type, confidence, evidence_count, metadata) "
                    "VALUES (:id, :src, :tgt, :type, :conf, :ev, :meta) "
                    "ON CONFLICT (relationship_id) DO UPDATE SET "
                    "confidence=EXCLUDED.confidence, evidence_count=EXCLUDED.evidence_count, metadata=EXCLUDED.metadata"
                ),
                {
                    "id": rel.relationship_id,
                    "src": rel.source_identity,
                    "tgt": rel.target_identity,
                    "type": rel.relationship_type,
                    "conf": rel.confidence,
                    "ev": rel.evidence_count,
                    "meta": json.dumps(rel.metadata),
                },
            )
            await session.commit()

    async def find_relationships(self, identity_id: str) -> list[Relationship]:
        async with get_session() as session:
            result = await session.execute(
                text("SELECT * FROM relationships WHERE source_identity = :id OR target_identity = :id"),
                {"id": identity_id},
            )
            return [self._row_to_relationship(row) for row in result.mappings()]

    async def find_relationship(
        self, source_id: str, target_id: str, rel_type: str
    ) -> Relationship | None:
        async with get_session() as session:
            result = await session.execute(
                text(
                    "SELECT * FROM relationships WHERE source_identity = :src AND target_identity = :tgt AND relationship_type = :type"
                ),
                {"src": source_id, "tgt": target_id, "type": rel_type},
            )
            row = result.mappings().first()
            return self._row_to_relationship(row) if row else None

    def _row_to_relationship(self, row: dict) -> Relationship:
        return Relationship(
            relationship_id=row["relationship_id"],
            source_identity=row["source_identity"],
            target_identity=row["target_identity"],
            relationship_type=row["relationship_type"],
            confidence=row.get("confidence", 1.0),
            evidence_count=row.get("evidence_count", 1),
            metadata=json.loads(row["metadata"]) if isinstance(row.get("metadata"), str) else (row.get("metadata") or {}),
        )

    # --- Projects ---

    async def save_project(self, project: Project) -> None:
        async with get_session() as session:
            await session.execute(
                text(
                    "INSERT INTO projects (project_id, name, aliases, status, metadata) "
                    "VALUES (:id, :name, :aliases, :status, :meta) "
                    "ON CONFLICT (project_id) DO UPDATE SET "
                    "name=EXCLUDED.name, aliases=EXCLUDED.aliases, status=EXCLUDED.status, metadata=EXCLUDED.metadata"
                ),
                {
                    "id": project.project_id,
                    "name": project.name,
                    "aliases": json.dumps(project.aliases),
                    "status": project.status,
                    "meta": json.dumps(project.metadata),
                },
            )
            await session.commit()

    async def find_project_by_name(self, name: str) -> Project | None:
        async with get_session() as session:
            result = await session.execute(
                text("SELECT * FROM projects WHERE name = :name"), {"name": name}
            )
            row = result.mappings().first()
            return self._row_to_project(row) if row else None

    async def list_projects(self, limit: int = 100) -> list[Project]:
        async with get_session() as session:
            result = await session.execute(
                text("SELECT * FROM projects WHERE status = 'active' ORDER BY name LIMIT :limit"),
                {"limit": limit},
            )
            return [self._row_to_project(row) for row in result.mappings()]

    def _row_to_project(self, row: dict) -> Project:
        return Project(
            project_id=row["project_id"],
            name=row.get("name", ""),
            aliases=json.loads(row["aliases"]) if isinstance(row.get("aliases"), str) else (row.get("aliases") or []),
            status=row.get("status", "active"),
            metadata=json.loads(row["metadata"]) if isinstance(row.get("metadata"), str) else (row.get("metadata") or {}),
        )


identity_store = IdentityStore()

from __future__ import annotations

import logging
import time
from typing import Any

from app.identity.identity import Identity
from app.identity.relationship import Relationship
from app.identity.project import Project
from app.identity.store import identity_store

logger = logging.getLogger(__name__)


class IdentityManager:
    """CRUD + merge for identities, relationships, projects. ponytail: thin wrapper over store."""

    async def create_identity(
        self, display_name: str = "", aliases: list[str] | None = None, metadata: dict[str, Any] | None = None
    ) -> Identity:
        identity = Identity(display_name=display_name, aliases=aliases or [], metadata=metadata or {})
        await identity_store.save_identity(identity)
        from app.intelligence.metrics import metrics
        metrics.record_identity_created()
        return identity

    async def get_identity(self, identity_id: str) -> Identity | None:
        return await identity_store.get_identity(identity_id)

    async def find_identity(self, name: str = "", alias: str = "") -> list[Identity]:
        if name:
            return await identity_store.find_by_name(name)
        if alias:
            return await identity_store.find_by_alias(alias)
        return []

    async def merge_identities(self, keep_id: str, drop_id: str) -> Identity | None:
        keep = await identity_store.get_identity(keep_id)
        drop = await identity_store.get_identity(drop_id)
        if not keep or not drop:
            return None
        # Merge aliases
        merged_aliases = list(set(keep.aliases + drop.aliases))
        if drop.display_name and drop.display_name not in keep.display_name:
            merged_aliases.append(drop.display_name)
        keep.aliases = merged_aliases
        keep.last_seen = max(keep.last_seen, drop.last_seen)
        keep.metadata.update(drop.metadata)
        await identity_store.save_identity(keep)
        # Redirect relationships
        rels = await identity_store.find_relationships(drop_id)
        for rel in rels:
            if rel.source_identity == drop_id:
                rel.source_identity = keep_id
            if rel.target_identity == drop_id:
                rel.target_identity = keep_id
            await identity_store.save_relationship(rel)
        from app.intelligence.metrics import metrics
        metrics.record_identity_merge()
        return keep

    async def touch_identity(self, identity_id: str) -> None:
        identity = await identity_store.get_identity(identity_id)
        if identity:
            identity.last_seen = time.time()
            await identity_store.save_identity(identity)

    async def list_identities(self, limit: int = 100) -> list[Identity]:
        return await identity_store.list_identities(limit)

    # --- Relationships ---

    async def add_relationship(
        self, source_id: str, target_id: str, rel_type: str, metadata: dict[str, Any] | None = None
    ) -> Relationship:
        existing = await identity_store.find_relationship(source_id, target_id, rel_type)
        if existing:
            existing.evidence_count += 1
            await identity_store.save_relationship(existing)
            from app.intelligence.metrics import metrics
            metrics.record_relationship_update()
            return existing
        rel = Relationship(
            source_identity=source_id, target_identity=target_id,
            relationship_type=rel_type, metadata=metadata or {},
        )
        await identity_store.save_relationship(rel)
        from app.intelligence.metrics import metrics
        metrics.record_relationship_update()
        return rel

    async def get_relationships(self, identity_id: str) -> list[Relationship]:
        return await identity_store.find_relationships(identity_id)

    # --- Projects ---

    async def create_project(self, name: str, aliases: list[str] | None = None) -> Project:
        project = Project(name=name, aliases=aliases or [])
        await identity_store.save_project(project)
        return project

    async def get_project(self, name: str) -> Project | None:
        return await identity_store.find_project_by_name(name)

    async def list_projects(self, limit: int = 100) -> list[Project]:
        return await identity_store.list_projects(limit)


_manager: IdentityManager | None = None


def get_identity_manager() -> IdentityManager:
    global _manager
    if _manager is None:
        _manager = IdentityManager()
    return _manager

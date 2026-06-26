from __future__ import annotations

import logging
import time
from typing import Any

from app.world.models import WorldEntity, WorldRelation, WorldAttribute
from app.world.store import world_store

logger = logging.getLogger(__name__)


async def update_from_knowledge(knowledge: "Knowledge") -> None:

    """Process a knowledge item into the world model. ponytail: resolve entity → resolve entity → store relation.

    This is the core integration point. Every knowledge item flows through here.
    """
    from app.knowledge.knowledge import Knowledge
    from app.intelligence.metrics import metrics

    try:
        # Resolve subject entity
        source = await _resolve_entity(knowledge.subject, knowledge.identity_id)
        # Resolve object entity
        target = await _resolve_entity(knowledge.object, knowledge.identity_id)

        # Store relation
        await _store_relation(source, target, knowledge)

        # Store predicate as attribute on source entity
        await _store_attribute(source, knowledge.predicate, knowledge.object)

        metrics.record_world_model_update()
    except Exception:
        logger.exception("World model update failed for knowledge %s", knowledge.knowledge_id)
        metrics.record_world_model_failure()


async def _resolve_entity(name: str, identity_id: str = "") -> WorldEntity:
    """Find or create a canonical entity. ponytail: exact match → alias match → create."""
    if not name:
        # ponytail: empty name → stub entity
        name = "unknown"

    # Exact name match
    entity = await world_store.find_entity_by_name(name)
    if entity:
        entity.updated_at = time.time()
        await world_store.save_entity(entity)
        return entity

    # Alias match
    entity = await world_store.find_entity_by_alias(name)
    if entity:
        # Add as alias if not already present
        if name not in entity.aliases:
            entity.aliases.append(name)
            entity.updated_at = time.time()
            await world_store.save_entity(entity)
        return entity

    # Create new entity
    entity = WorldEntity(
        name=name,
        aliases=[name] if name else [],
        metadata={"identity_id": identity_id} if identity_id else {},
    )
    await world_store.save_entity(entity)
    return entity


async def _store_relation(source: WorldEntity, target: WorldEntity, knowledge: "Knowledge") -> None:
    """Find or create relation between two entities. ponytail: dedup by source+target+type."""
    from app.knowledge.knowledge import Knowledge

    existing = await world_store.find_relation(source.entity_id, target.entity_id, knowledge.predicate)
    if existing:
        existing.evidence_count += 1
        existing.updated_at = time.time()
        if knowledge.knowledge_id not in existing.source_knowledge_ids:
            existing.source_knowledge_ids.append(knowledge.knowledge_id)
        await world_store.save_relation(existing)
        return

    rel = WorldRelation(
        source_entity=source.entity_id,
        target_entity=target.entity_id,
        relation_type=knowledge.predicate,
        source_knowledge_ids=[knowledge.knowledge_id],
        metadata={"identity_id": knowledge.identity_id} if knowledge.identity_id else {},
    )
    await world_store.save_relation(rel)


async def _store_attribute(entity: WorldEntity, key: str, value: str) -> None:
    """Store an attribute on an entity. ponytail: upsert by entity+key."""
    existing = await world_store.find_attribute(entity.entity_id, key)
    if existing:
        if existing.attr_value != value:
            existing.attr_value = value
            existing.updated_at = time.time()
            await world_store.save_attribute(existing)
        return

    attr = WorldAttribute(
        entity_id=entity.entity_id,
        attr_key=key,
        attr_value=value,
    )
    await world_store.save_attribute(attr)


async def find_entity(name: str) -> WorldEntity | None:
    """Find entity by name or alias."""
    entity = await world_store.find_entity_by_name(name)
    if entity:
        return entity
    return await world_store.find_entity_by_alias(name)


async def find_by_alias(alias: str) -> WorldEntity | None:
    return await world_store.find_entity_by_alias(alias)


async def find_relations(entity_id: str) -> list[WorldRelation]:
    return await world_store.find_relations_by_entity(entity_id)


async def get_entity(entity_id: str) -> WorldEntity | None:
    return await world_store.get_entity(entity_id)


async def get_attributes(entity_id: str) -> list[WorldAttribute]:
    return await world_store.find_attributes(entity_id)


async def list_entities(entity_type: str = "", limit: int = 100) -> list[WorldEntity]:
    return await world_store.list_entities(entity_type, limit)


async def count(entity_type: str = "") -> int:
    return await world_store.count_entities(entity_type)


async def merge_entities(keep_id: str, drop_id: str) -> WorldEntity | None:
    """Merge two entities. ponytail: keep the one with more aliases, redirect relations."""
    keep = await world_store.get_entity(keep_id)
    drop = await world_store.get_entity(drop_id)
    if not keep or not drop:
        return None

    # Merge aliases
    merged_aliases = list(set(keep.aliases + drop.aliases))
    if drop.name and drop.name not in keep.name:
        merged_aliases.append(drop.name)
    keep.aliases = merged_aliases
    keep.updated_at = time.time()
    keep.metadata.update(drop.metadata)
    await world_store.save_entity(keep)

    # Redirect relations
    await world_store.redirect_relations(drop_id, keep_id)

    # Merge attributes
    drop_attrs = await world_store.find_attributes(drop_id)
    for attr in drop_attrs:
        existing = await world_store.find_attribute(keep_id, attr.attr_key)
        if not existing:
            attr.entity_id = keep_id
            await world_store.save_attribute(attr)

    # Delete dropped entity and its attributes
    await world_store.delete_attributes(drop_id)
    await world_store.delete_entity(drop_id)

    # Update beliefs referencing merged entity
    try:
        from app.belief.manager import on_world_entity_merged
        await on_world_entity_merged(keep_id, drop_id)
    except Exception:
        logger.debug("Belief update failed for entity merge %s->%s", drop_id, keep_id, exc_info=True)

    from app.intelligence.metrics import metrics
    metrics.record_world_model_merge()
    return keep


async def merge_relations(keep_id: str, drop_id: str) -> WorldRelation | None:
    """Merge two relations of the same type. ponytail: combine evidence, delete drop."""
    keep = await world_store.get_entity(keep_id)
    drop = await world_store.get_entity(drop_id)
    if not keep or not drop:
        return None

    # Find all relations for both entities
    keep_rels = await world_store.find_relations_by_entity(keep_id)
    drop_rels = await world_store.find_relations_by_entity(drop_id)

    # Find matching relations (same type, same direction after redirect)
    for dr in drop_rels:
        # Redirect drop entity references to keep
        src = keep_id if dr.source_entity == drop_id else dr.source_entity
        tgt = keep_id if dr.target_entity == drop_id else dr.target_entity

        existing = await world_store.find_relation(src, tgt, dr.relation_type)
        if existing:
            existing.evidence_count += dr.evidence_count
            existing.updated_at = time.time()
            for kid in dr.source_knowledge_ids:
                if kid not in existing.source_knowledge_ids:
                    existing.source_knowledge_ids.append(kid)
            await world_store.save_relation(existing)
            await world_store.delete_relation(dr.relation_id)
        else:
            dr.source_entity = src
            dr.target_entity = tgt
            dr.updated_at = time.time()
            await world_store.save_relation(dr)

    from app.intelligence.metrics import metrics
    metrics.record_world_model_merge()
    return keep

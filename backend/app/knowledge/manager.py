from __future__ import annotations

import logging
import time

from app.knowledge.extractor import extract
from app.knowledge.knowledge import Knowledge
from app.knowledge.store import knowledge_store
from app.memory.memory import Memory

logger = logging.getLogger(__name__)


async def process_memory(memory: Memory) -> list[Knowledge]:
    """Extract knowledge from a memory and store it. ponytail: extract → dedup → store."""
    from app.intelligence.metrics import metrics

    candidates = extract(memory)
    stored: list[Knowledge] = []

    for k in candidates:
        existing = await knowledge_store.find_duplicate(k.subject, k.predicate, k.object, k.identity_id)
        if existing:
            # Merge: add this memory to source list, update timestamp
            if memory.memory_id not in existing.source_memory_ids:
                existing.source_memory_ids.append(memory.memory_id)
                existing.updated_at = time.time()
                await knowledge_store.update(existing)
                metrics.record_knowledge_updated()
            continue

        await knowledge_store.append(k)
        metrics.record_knowledge_created()
        stored.append(k)

    return stored


async def retrieve(
    query: str = "",
    identity_id: str = "",
    limit: int = 50,
) -> list[Knowledge]:
    """Retrieve knowledge. ponytail: subject match or recent."""
    from app.intelligence.metrics import metrics
    metrics.record_knowledge_query()

    if query:
        return await knowledge_store.find_by_subject(query, identity_id, limit)
    return await knowledge_store.list_recent(identity_id, limit)


async def find_by_subject(subject: str, identity_id: str = "", limit: int = 50) -> list[Knowledge]:
    from app.intelligence.metrics import metrics
    metrics.record_knowledge_query()
    return await knowledge_store.find_by_subject(subject, identity_id, limit)


async def find_by_identity(identity_id: str, limit: int = 50) -> list[Knowledge]:
    from app.intelligence.metrics import metrics
    metrics.record_knowledge_query()
    return await knowledge_store.find_by_identity(identity_id, limit)


async def find_by_predicate(predicate: str, identity_id: str = "", limit: int = 50) -> list[Knowledge]:
    from app.intelligence.metrics import metrics
    metrics.record_knowledge_query()
    return await knowledge_store.find_by_predicate(predicate, identity_id, limit)


async def update(knowledge: Knowledge) -> None:
    from app.intelligence.metrics import metrics
    knowledge.updated_at = time.time()
    await knowledge_store.update(knowledge)
    metrics.record_knowledge_updated()


async def list_recent(identity_id: str = "", limit: int = 50) -> list[Knowledge]:
    from app.intelligence.metrics import metrics
    metrics.record_knowledge_query()
    return await knowledge_store.list_recent(identity_id, limit)


async def get(knowledge_id: str) -> Knowledge | None:
    return await knowledge_store.get(knowledge_id)


async def count(identity_id: str = "") -> int:
    return await knowledge_store.count(identity_id)

from __future__ import annotations

import logging
import time

from app.memory.classifier import classify
from app.memory.memory import Memory, MemoryType
from app.memory.store import memory_store
from app.observation.observation import Observation

logger = logging.getLogger(__name__)

# ponytail: importance threshold — observations below this are skipped.
IMPORTANCE_THRESHOLD = 0.2


async def evaluate(observation: Observation) -> Memory | None:
    """Evaluate an observation and create a memory if important enough.

    ponytail: classify → threshold → store. One function, no class.
    Returns Memory if created, None if skipped.
    """
    from app.intelligence.metrics import metrics

    memory_type, importance = classify(observation)

    if importance < IMPORTANCE_THRESHOLD:
        metrics.record_memory_skipped()
        return None

    memory = Memory(
        observation_id=observation.observation_id,
        identity_id=observation.identity_id,
        memory_type=memory_type,
        importance=importance,
        summary=observation.summary,
        content=_build_content(observation),
        metadata={
            "observation_type": observation.observation_type.value,
            "source": observation.source,
            "actor": observation.actor,
        },
    )

    await memory_store.append(memory)
    metrics.record_memory_created(importance)

    # ponytail: extract knowledge from new memory, don't block caller on failure
    try:
        from app.knowledge.manager import process_memory
        await process_memory(memory)
    except Exception:
        logger.debug("Knowledge extraction failed for memory %s", memory.memory_id, exc_info=True)

    return memory


def _build_content(observation: Observation) -> str:
    """Extract searchable content from observation. ponytail: summary + payload."""
    parts = [observation.summary]
    payload = observation.payload
    if isinstance(payload, dict):
        for key in ("query", "content", "text", "message", "response"):
            if key in payload and payload[key]:
                parts.append(str(payload[key]))
    return "\n".join(parts)


async def retrieve(
    query: str = "",
    memory_type: MemoryType | None = None,
    identity_id: str = "",
    limit: int = 20,
) -> list[Memory]:
    """Retrieve memories. ponytail: type filter or recent, no vector search here."""
    if memory_type:
        memories = await memory_store.list_by_type(memory_type, identity_id, limit)
    else:
        memories = await memory_store.list_recent(identity_id, limit)

    for m in memories:
        await memory_store.touch(m.memory_id)

    return memories


async def retrieve_working(identity_id: str = "", limit: int = 10) -> list[Memory]:
    return await retrieve(memory_type=MemoryType.WORKING, identity_id=identity_id, limit=limit)


async def retrieve_episodic(identity_id: str = "", limit: int = 20) -> list[Memory]:
    return await retrieve(memory_type=MemoryType.EPISODIC, identity_id=identity_id, limit=limit)


async def retrieve_semantic(identity_id: str = "", limit: int = 20) -> list[Memory]:
    return await retrieve(memory_type=MemoryType.SEMANTIC, identity_id=identity_id, limit=limit)


async def retrieve_historical(identity_id: str = "", limit: int = 20) -> list[Memory]:
    return await retrieve(memory_type=MemoryType.HISTORICAL, identity_id=identity_id, limit=limit)


async def retrieve_recent(identity_id: str = "", limit: int = 20) -> list[Memory]:
    return await retrieve(identity_id=identity_id, limit=limit)


async def store_memory(memory: Memory) -> None:
    """Directly store a pre-built memory. ponytail: pass-through for API use."""
    await memory_store.append(memory)


async def touch(memory_id: str) -> None:
    await memory_store.touch(memory_id)

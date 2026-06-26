import hashlib
import logging
import time
from datetime import datetime, timezone

from fastapi import APIRouter, Depends

from app.core.dependencies import get_chroma, get_redis
from app.intelligence.deduplicator import content_hash
from app.intelligence.metrics import metrics
from app.memory.classifier import classify
from app.memory.memory import Memory, MemoryType
from app.memory.store import memory_store
from app.models.store import MemoryStatsResponse, StoreRequest, StoreResponse
from app.observation.observation import Observation, ObservationType
from app.providers.factory import get_provider
from app.services.chroma_service import ChromaService
from app.services.redis_service import RedisService
# ponytail: emit imported lazily

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/memory", tags=["memory"])


@router.post("/store", response_model=StoreResponse)
async def store_memory(
    body: StoreRequest,
    chroma: ChromaService = Depends(get_chroma),
    redis: RedisService = Depends(get_redis),
):
    content = body.content.strip()

    if not content:
        return StoreResponse(status="stored")

    # Create observation from API request
    observation = Observation(
        observation_type=ObservationType.USER_MESSAGE if body.role == "user" else ObservationType.ASSISTANT_RESPONSE,
        source=body.source,
        actor=body.role,
        summary=content[:200],
        payload={"content": content, "role": body.role},
    )

    memory_type, importance = classify(observation)

    # Dedup check via content hash
    norm_hash = content_hash(content)
    existing_hashes = set()
    try:
        collection = chroma.client.get_or_create_collection(name="conversations")
        all_docs = collection.get(include=["metadatas"])
        if all_docs.get("metadatas"):
            for meta in all_docs["metadatas"]:
                if meta.get("content_hash"):
                    existing_hashes.add(meta["content_hash"])
    except Exception:
        pass

    if norm_hash in existing_hashes:
        metrics.record_store(is_duplicate=True)
        return StoreResponse(status="duplicate")

    # Create and persist memory to PostgreSQL
    memory = Memory(
        observation_id=observation.observation_id,
        memory_type=memory_type,
        importance=importance,
        summary=content[:200],
        content=content,
        metadata={"role": body.role, "source": body.source},
    )
    await memory_store.append(memory)
    # Trigger knowledge extraction for the new memory
    try:
        from app.knowledge.manager import process_memory
        await process_memory(memory)
    except Exception:
        logger.debug("Knowledge extraction failed for memory %s", memory.memory_id, exc_info=True)

    # Also store in ChromaDB for semantic retrieval
    timestamp = datetime.now(tz=timezone.utc).isoformat()
    doc_id = hashlib.sha256(f"{content}{timestamp}".encode()).hexdigest()

    provider = get_provider()
    embeddings = await provider.embed([content])

    chroma.upsert(
        ids=[doc_id],
        embeddings=embeddings,
        documents=[content],
        metadatas=[{
            "role": body.role,
            "source": body.source,
            "timestamp": timestamp,
            "conversation_id": "live_kio",
            "memory_type": memory_type.value,
            "importance": importance,
            "content_hash": norm_hash,
        }],
    )

    metrics.record_store(is_duplicate=False)
    metrics.record_memory_created(importance)
    from app.main import emit  # lazy import
    await emit("memory_stored", source="api/store", payload={"memory_type": memory_type.value, "importance": importance, "role": body.role, "content": content})
    return StoreResponse(status="stored", memory_type=memory_type.value, importance=round(importance * 100))


@router.get("/stats", response_model=MemoryStatsResponse)
async def memory_stats(
    chroma: ChromaService = Depends(get_chroma),
):
    all_chunks = chroma.get_all_metadata()

    total = len(all_chunks)
    conversations = {c.get("conversation_id", "") for c in all_chunks}
    lengths = [len(c.get("text", "")) for c in all_chunks]

    # Count by canonical memory types
    type_counts = {"working": 0, "episodic": 0, "semantic": 0, "historical": 0}
    timestamps = []
    for c in all_chunks:
        mt = c.get("memory_type", "")
        # Map old types to new canonical types
        mapped = _map_type(mt)
        if mapped in type_counts:
            type_counts[mapped] += 1
        ts = c.get("timestamp", "")
        if ts:
            timestamps.append(ts)

    return MemoryStatsResponse(
        total_chunks=total,
        total_conversations=len(conversations),
        duplicates_skipped=metrics.duplicate_skip_count,
        short_term=type_counts["working"] + type_counts["episodic"],
        long_term=type_counts["semantic"],
        ephemeral=type_counts["historical"],
        average_chunk_length=round(sum(lengths) / max(total, 1), 1),
        oldest_memory=min(timestamps) if timestamps else "",
        newest_memory=max(timestamps) if timestamps else "",
    )


def _map_type(old_type: str) -> str:
    """Map old memory types to canonical types. ponytail: flat dict."""
    return {
        "long_term": "semantic",
        "short_term": "working",
        "ephemeral": "historical",
        "working": "working",
        "episodic": "episodic",
        "semantic": "semantic",
        "historical": "historical",
    }.get(old_type, "historical")

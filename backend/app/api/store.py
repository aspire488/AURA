import hashlib
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends

from app.core.dependencies import get_chroma, get_redis
from app.intelligence.deduplicator import content_hash
from app.intelligence.memory_classifier import classify_memory
from app.intelligence.memory_ranker import score_importance
from app.intelligence.metrics import metrics
from app.models.store import MemoryStatsResponse, StoreRequest, StoreResponse
from app.providers.factory import get_provider
from app.services.chroma_service import ChromaService
from app.services.redis_service import RedisService
from app.main import emit

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

    memory_type = classify_memory(body.role, content)
    importance = score_importance(body.role, content)

    timestamp = datetime.now(tz=timezone.utc).isoformat()
    doc_id = hashlib.sha256(f"{content}{timestamp}".encode()).hexdigest()

    # Dedup check
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
            "memory_type": memory_type,
            "importance": importance,
            "content_hash": norm_hash,
        }],
    )

    metrics.record_store(is_duplicate=False)
    await emit("memory_stored", source="api/store", payload={"memory_type": memory_type, "importance": importance, "role": body.role})
    return StoreResponse(status="stored", memory_type=memory_type, importance=importance)


@router.get("/stats", response_model=MemoryStatsResponse)
async def memory_stats(
    chroma: ChromaService = Depends(get_chroma),
):
    all_chunks = chroma.get_all_metadata()

    total = len(all_chunks)
    conversations = {c.get("conversation_id", "") for c in all_chunks}
    lengths = [len(c.get("text", "")) for c in all_chunks]

    type_counts = {"short_term": 0, "long_term": 0, "ephemeral": 0}
    timestamps = []
    for c in all_chunks:
        mt = c.get("memory_type", "")
        if mt in type_counts:
            type_counts[mt] += 1
        ts = c.get("timestamp", "")
        if ts:
            timestamps.append(ts)

    return MemoryStatsResponse(
        total_chunks=total,
        total_conversations=len(conversations),
        duplicates_skipped=metrics.duplicate_skip_count,
        short_term=type_counts["short_term"],
        long_term=type_counts["long_term"],
        ephemeral=type_counts["ephemeral"],
        average_chunk_length=round(sum(lengths) / max(total, 1), 1),
        oldest_memory=min(timestamps) if timestamps else "",
        newest_memory=max(timestamps) if timestamps else "",
    )

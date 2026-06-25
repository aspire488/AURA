from __future__ import annotations

import hashlib
from datetime import datetime, timezone

from app.core.dependencies import get_chroma, get_redis
from app.intelligence.deduplicator import content_hash
from app.intelligence.memory_classifier import classify_memory
from app.intelligence.memory_ranker import score_importance
from app.intelligence.summarizer import summarize_conversation
from app.intelligence.metrics import metrics
from app.services.chroma_service import ChromaService
from app.services.redis_service import RedisService


class MemoryAdapter:
    """Single interface over Chroma + Redis.

    ponytail: delegates to existing services, no new abstractions.
    """

    def __init__(self, chroma: ChromaService | None = None, redis: RedisService | None = None):
        self._chroma = chroma or get_chroma()
        self._redis = redis or get_redis()

    async def store(
        self,
        content: str,
        role: str = "user",
        source: str = "runtime",
        conversation_id: str = "live_kio",
    ) -> dict:
        content = content.strip()
        if not content:
            return {"status": "empty"}

        memory_type = classify_memory(role, content)
        importance = score_importance(role, content)
        norm_hash = content_hash(content)

        # Dedup check
        existing = set()
        try:
            collection = self._chroma.client.get_or_create_collection(name="conversations")
            all_docs = collection.get(include=["metadatas"])
            if all_docs.get("metadatas"):
                for meta in all_docs["metadatas"]:
                    if meta.get("content_hash"):
                        existing.add(meta["content_hash"])
        except Exception:
            pass

        if norm_hash in existing:
            metrics.record_store(is_duplicate=True)
            return {"status": "duplicate"}

        from app.providers.factory import get_provider
        provider = get_provider()
        embeddings = await provider.embed([content])

        timestamp = datetime.now(tz=timezone.utc).isoformat()
        doc_id = hashlib.sha256(f"{content}{timestamp}".encode()).hexdigest()

        self._chroma.upsert(
            ids=[doc_id],
            embeddings=embeddings,
            documents=[content],
            metadatas=[{
                "role": role,
                "source": source,
                "timestamp": timestamp,
                "conversation_id": conversation_id,
                "memory_type": memory_type,
                "importance": importance,
                "content_hash": norm_hash,
            }],
        )

        metrics.record_store(is_duplicate=False)
        return {"status": "stored", "memory_type": memory_type, "importance": importance}

    def retrieve(self, embedding: list[float], top_k: int = 10) -> list[dict]:
        return self._chroma.query(embedding, top_k=top_k)

    def retrieve_by_keyword(self, query: str, top_k: int = 10) -> list[dict]:
        return self._chroma.keyword_search(query, top_k=top_k)

    def retrieve_by_conversation(self, conversation_id: str) -> list[dict]:
        return self._chroma.get_by_conversation_id(conversation_id)

    def summarize_conversation(self, conversation_id: str) -> dict:
        chunks = self._chroma.get_by_conversation_id(conversation_id)
        return summarize_conversation(chunks)

    def stats(self) -> dict:
        all_chunks = self._chroma.get_all_metadata()
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
        return {
            "total_chunks": total,
            "total_conversations": len(conversations),
            "short_term": type_counts["short_term"],
            "long_term": type_counts["long_term"],
            "ephemeral": type_counts["ephemeral"],
            "average_chunk_length": round(sum(lengths) / max(total, 1), 1),
            "oldest_memory": min(timestamps) if timestamps else "",
            "newest_memory": max(timestamps) if timestamps else "",
        }

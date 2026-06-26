from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timezone

from app.core.dependencies import get_chroma, get_redis
from app.intelligence.deduplicator import content_hash
from app.intelligence.metrics import metrics
from app.memory.classifier import classify
from app.memory.memory import Memory, MemoryType
from app.memory.store import memory_store
from app.observation.observation import Observation, ObservationType
from app.services.chroma_service import ChromaService
from app.services.redis_service import RedisService
from app.main import emit


class MemoryAdapter:
    """Single interface over Chroma + Redis + Memory store.

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

        # Create observation for classification
        observation = Observation(
            observation_type=ObservationType.USER_MESSAGE if role == "user" else ObservationType.ASSISTANT_RESPONSE,
            source=source,
            actor=role,
            summary=content[:200],
            payload={"content": content, "role": role},
        )

        memory_type, importance = classify(observation)
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

        # Create and persist memory to PostgreSQL
        memory = Memory(
            observation_id=observation.observation_id,
            memory_type=memory_type,
            importance=importance,
            summary=content[:200],
            content=content,
            metadata={"role": role, "source": source, "conversation_id": conversation_id},
        )
        await memory_store.append(memory)

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
                "memory_type": memory_type.value,
                "importance": importance,
                "content_hash": norm_hash,
            }],
        )

        metrics.record_store(is_duplicate=False)
        metrics.record_memory_created(importance)
        await emit("memory_stored", session_id=conversation_id, source="memory_adapter", payload={"memory_type": memory_type.value, "importance": importance, "role": role})
        return {"status": "stored", "memory_type": memory_type.value, "importance": importance}

import asyncio
import datetime
from typing import List

from app.core.dependencies import get_chroma, get_redis
from app.providers.factory import get_provider

# ponytail: simple idle threshold (seconds) – adjust as needed
IDLE_THRESHOLD_SECONDS = 3600  # 1 hour

async def _fetch_idle_conversation_ids(redis) -> List[str]:
    """Return conversation IDs whose last update timestamp is older than the idle threshold."""
    now_ts = datetime.datetime.now(tz=datetime.timezone.utc).timestamp()
    max_score = now_ts - IDLE_THRESHOLD_SECONDS
    # Redis sorted set score is timestamp of last update
    ids = await redis.client.zrangebyscore("conv:index", "-inf", max_score)
    return [cid for cid in ids]

async def consolidate_idle_memories() -> None:
    """Flush idle conversation logs from Redis into ChromaDB and clean up Redis.

    Steps:
    1. Find idle conversation IDs.
    2. Retrieve their stored messages from Chroma.
    3. Concatenate texts, embed, and upsert as a single semantic chunk linked to the identity.
    4. Remove the conversation hash and its index entry from Redis.
    """
    redis = get_redis()
    chroma = get_chroma()
    provider = get_provider()

    idle_ids = await _fetch_idle_conversation_ids(redis)
    if not idle_ids:
        return

    for conv_id in idle_ids:
        # Pull existing chunks – they already have embeddings, but we create a summary chunk
        chunks = chroma.get_by_conversation_id(conv_id)
        if not chunks:
            # Nothing to consolidate – just clean up the Redis entry
            await redis.client.delete(f"conv:{conv_id}")
            await redis.client.zrem("conv:index", conv_id)
            continue

        # Concatenate all texts into one block
        combined_text = "\n\n".join(chunk.get("text", "") for chunk in chunks)
        # Use provider to embed the combined block
        embedding = await provider.embed([combined_text])

        # Identity handling – optional, default empty if not present
        # For simplicity, we look for an "identity_id" field in metadata of first chunk
        identity_id = chunks[0].get("metadata", {}).get("identity_id", "")

        doc_id = f"idle-{conv_id}"
        chroma.upsert(
            ids=[doc_id],
            embeddings=embedding,
            documents=[combined_text],
            metadatas=[{"conversation_id": conv_id, "identity_id": identity_id, "source": "idle_consolidation"}],
        )

        # Clean up Redis entries
        await redis.client.delete(f"conv:{conv_id}")
        await redis.client.zrem("conv:index", conv_id)

    # Ensure all commands are flushed
    await redis.client.bgsave()

# ponytail: expose for daemon import
__all__ = ["consolidate_idle_memories"]

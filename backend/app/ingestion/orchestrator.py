import asyncio
import logging
from datetime import datetime, timezone

from app.core.dependencies import get_chroma, get_redis
from app.ingestion.chunker import chunk_messages
from app.ingestion.loader import load_conversation_batch, scan_source_files
from app.ingestion.parser import parse_conversation
from app.providers.factory import get_provider

logger = logging.getLogger(__name__)


def _extract_title(conv: dict) -> str:
    mapping = conv.get("mapping", {})
    for node in mapping.values():
        msg = node.get("message")
        if msg is None:
            continue
        if msg.get("author", {}).get("role") != "user":
            continue
        parts = msg.get("content", {}).get("parts", [])
        text = " ".join(p for p in parts if isinstance(p, str)).strip()
        if text:
            return text[:200]
    return "Untitled"


async def _store_conversation_metadata(redis, conv: dict, message_count: int):
    conversation_id = conv.get("id") or conv.get("conversation_id", "")
    if not conversation_id:
        return
    key = f"conv:{conversation_id}"
    now = datetime.now(tz=timezone.utc).isoformat()
    existing = await redis.client.hgetall(key)
    title = _extract_title(conv) if not existing else existing.get("title", _extract_title(conv))
    await redis.client.hset(key, mapping={
        "conversation_id": conversation_id,
        "title": title,
        "source": "chatgpt_export",
        "created_at": existing.get("created_at", now),
        "updated_at": now,
        "message_count": str(message_count),
        "summary": existing.get("summary", ""),
    })
    await redis.client.zadd("conv:index", {conversation_id: datetime.now(tz=timezone.utc).timestamp()})

async def start_ingestion(limit: int | None = None) -> dict:
    redis = get_redis()
    status = await redis.client.get("ingestion:status")
    if status == "running":
        job_id = await redis.client.get("ingestion:latest")
        return {"job_id": job_id, "status": "already_running"}

    job_id = f"ingest-{datetime.now(tz=timezone.utc).strftime('%Y%m%d-%H%M%S')}"

    await redis.client.set("ingestion:latest", job_id)
    await redis.client.set("ingestion:status", "running")
    await redis.client.hset(f"ingestion:{job_id}", mapping={
        "status": "running",
        "total": "0",
        "processed": "0",
        "errors": "0",
        "started_at": datetime.now(tz=timezone.utc).isoformat(),
    })

    asyncio.create_task(_run_ingestion(job_id, limit))
    return {"job_id": job_id, "status": "started"}


async def _run_ingestion(job_id: str, limit: int | None) -> None:
    chroma = get_chroma()
    redis = get_redis()
    provider = get_provider()

    try:
        collection = chroma.client.get_or_create_collection(
            name="conversations",
            metadata={"source": "chatgpt_export", "created": datetime.now(tz=timezone.utc).isoformat()},
        )

        source_files = scan_source_files()
        remaining = limit
        total = 0

        for file_path in source_files:
            if remaining is not None and remaining <= 0:
                break
            conversations = load_conversation_batch(file_path, remaining)

            for conv in conversations:
                if remaining is not None and remaining <= 0:
                    break
                try:
                    messages = parse_conversation(conv)
                    if not messages:
                        continue
                    chunks = chunk_messages(messages)

                    dedup_ids = []
                    dedup_texts = []
                    dedup_metas = []

                    for c in chunks:
                        dedup_key = f"dedup:message:{c['chunk_id']}"
                        if await redis.client.exists(dedup_key):
                            continue
                        dedup_ids.append(c["chunk_id"])
                        dedup_texts.append(c["text"])
                        dedup_metas.append({
                            "message_id": c["message_id"],
                            "conversation_id": c["conversation_id"],
                            "role": c["role"],
                            "timestamp": c["timestamp"],
                            "source": "chatgpt_export",
                        })

                    if not dedup_ids:
                        total += 1
                        await redis.client.hset(f"ingestion:{job_id}", mapping={
                            "status": "running",
                            "total": str(total),
                            "processed": str(total),
                        })
                        continue

                    embeddings = await provider.embed(dedup_texts)

                    collection.upsert(
                        ids=dedup_ids,
                        embeddings=embeddings,
                        documents=dedup_texts,
                        metadatas=dedup_metas,
                    )

                    for did in dedup_ids:
                        await redis.client.set(f"dedup:message:{did}", "1", ex=2592000)

                    await _store_conversation_metadata(redis, conv, len(chunks))

                    total += 1
                    await redis.client.hset(f"ingestion:{job_id}", mapping={
                        "status": "running",
                        "total": str(total),
                        "processed": str(total),
                    })

                    if remaining is not None:
                        remaining -= 1

                except Exception as exc:
                    logger.exception("Ingestion error for conversation %s: %s", conv.get("conversation_id", "?"), exc)
                    await redis.client.hincrby(f"ingestion:{job_id}", "errors", 1)

        await redis.client.hset(f"ingestion:{job_id}", mapping={
            "status": "completed",
            "total": str(total),
            "processed": str(total),
            "completed_at": datetime.now(tz=timezone.utc).isoformat(),
        })
        await redis.client.set("ingestion:status", "idle")

    except Exception as exc:
        await redis.client.hset(f"ingestion:{job_id}", mapping={
            "status": "failed",
            "error": str(exc),
            "completed_at": datetime.now(tz=timezone.utc).isoformat(),
        })
        await redis.client.set("ingestion:status", "idle")


async def get_status() -> dict | None:
    redis = get_redis()
    job_id = await redis.client.get("ingestion:latest")
    if not job_id:
        return None
    data = await redis.client.hgetall(f"ingestion:{job_id}")
    if not data:
        return None
    # Convert numeric strings
    result = {
        "job_id": job_id,
        "status": data.get("status"),
        "total": int(data.get("total", 0)),
        "processed": int(data.get("processed", 0)),
        "errors": int(data.get("errors", 0)),
        "started_at": data.get("started_at"),
        "completed_at": data.get("completed_at"),
        "error": data.get("error"),
    }
    return result

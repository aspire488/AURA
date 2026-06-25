from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.dependencies import get_chroma, get_redis
from app.models.conversation import (
    ConversationChunk,
    ConversationDetailResponse,
    ConversationListResponse,
    ConversationSummary,
)
from app.services.chroma_service import ChromaService
from app.services.redis_service import RedisService

router = APIRouter(prefix="/conversations", tags=["conversations"])


@router.get("", response_model=ConversationListResponse)
async def list_conversations(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    redis: RedisService = Depends(get_redis),
):
    total = await redis.client.zcard("conv:index")
    # ponytail: zrevrange for most-recent-first
    ids = await redis.client.zrevrange("conv:index", offset, offset + limit - 1)
    items = []
    for cid in ids:
        data = await redis.client.hgetall(f"conv:{cid}")
        if data:
            items.append(ConversationSummary(
                conversation_id=cid,
                title=data.get("title", ""),
                message_count=int(data.get("message_count", 0)),
                updated_at=data.get("updated_at", ""),
            ))
    return ConversationListResponse(total=total, items=items)


@router.get("/search", response_model=ConversationListResponse)
async def search_conversations(
    q: str = Query(..., min_length=1),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    redis: RedisService = Depends(get_redis),
):
    # ponytail: scan all conv keys, filter by substring match on title/summary/source
    matches = []
    cursor = 0
    while True:
        cursor, keys = await redis.client.scan(cursor, match="conv:*", count=500)
        for key in keys:
            data = await redis.client.hgetall(key)
            if not data:
                continue
            searchable = " ".join([
                data.get("title", ""),
                data.get("summary", ""),
                data.get("source", ""),
                data.get("conversation_id", ""),
            ]).lower()
            if q.lower() in searchable:
                cid = key.removeprefix("conv:")
                matches.append(ConversationSummary(
                    conversation_id=cid,
                    title=data.get("title", ""),
                    message_count=int(data.get("message_count", 0)),
                    updated_at=data.get("updated_at", ""),
                ))
        if cursor == 0:
            break
    total = len(matches)
    items = matches[offset:offset + limit]
    return ConversationListResponse(total=total, items=items)


@router.get("/{conversation_id}", response_model=ConversationDetailResponse)
async def get_conversation(
    conversation_id: str,
    redis: RedisService = Depends(get_redis),
    chroma: ChromaService = Depends(get_chroma),
):
    data = await redis.client.hgetall(f"conv:{conversation_id}")
    if not data:
        raise HTTPException(status_code=404, detail="Conversation not found")
    chunks = chroma.get_by_conversation_id(conversation_id)
    return ConversationDetailResponse(
        conversation_id=conversation_id,
        title=data.get("title", ""),
        source=data.get("source", ""),
        created_at=data.get("created_at", ""),
        updated_at=data.get("updated_at", ""),
        message_count=int(data.get("message_count", 0)),
        summary=data.get("summary") or None,
        messages=[ConversationChunk(**c) for c in chunks],
        chunk_count=len(chunks),
    )


@router.delete("/{conversation_id}")
async def delete_conversation(
    conversation_id: str,
    redis: RedisService = Depends(get_redis),
    chroma: ChromaService = Depends(get_chroma),
):
    data = await redis.client.hgetall(f"conv:{conversation_id}")
    if not data:
        raise HTTPException(status_code=404, detail="Conversation not found")
    chroma.delete_by_conversation_id(conversation_id)
    await redis.client.delete(f"conv:{conversation_id}")
    await redis.client.zrem("conv:index", conversation_id)
    return {"status": "deleted"}

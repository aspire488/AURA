import hashlib
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends

from app.core.dependencies import get_chroma
from app.models.store import StoreRequest, StoreResponse
from app.providers.factory import get_provider
from app.services.chroma_service import ChromaService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/memory", tags=["memory"])


@router.post("/store", response_model=StoreResponse)
async def store_memory(
    body: StoreRequest,
    chroma: ChromaService = Depends(get_chroma),
):
    content = body.content.strip()

    if not content:
        return StoreResponse(status="stored")

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
        }],
    )

    return StoreResponse(status="stored")

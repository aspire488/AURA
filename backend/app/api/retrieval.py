from fastapi import APIRouter, Depends

from app.core.dependencies import get_chroma
from app.models.query import QueryRequest, QueryResponse, QueryResult
from app.providers.factory import get_provider
from app.services.chroma_service import ChromaService

router = APIRouter(prefix="/retrieval", tags=["retrieval"])


@router.post("/query", response_model=QueryResponse)
async def query_endpoint(
    body: QueryRequest,
    chroma: ChromaService = Depends(get_chroma),
):
    provider = get_provider()
    embeddings = await provider.embed([body.query])
    results = chroma.query(embeddings[0], top_k=body.top_k)
    return QueryResponse(results=[QueryResult(**r) for r in results])

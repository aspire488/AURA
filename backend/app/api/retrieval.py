from fastapi import APIRouter, Depends

from app.core.dependencies import get_chroma
from app.intelligence.context_builder import ContextChunk, build_context
from app.intelligence.query_planner import classify_query
from app.intelligence.retriever import hybrid_search
from app.models.query import (
    ContextRequest,
    ContextResponse,
    ContextChunkResponse,
    QueryRequest,
    QueryResponse,
    QueryResult,
)
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


@router.post("/context", response_model=ContextResponse)
async def context_endpoint(
    body: ContextRequest,
    chroma: ChromaService = Depends(get_chroma),
):
    query_type = classify_query(body.query)
    provider = get_provider()
    embeddings = await provider.embed([body.query])

    results = hybrid_search(chroma, body.query, embeddings[0], top_k=body.top_k)

    bundle = build_context(
        query=body.query,
        query_type=query_type,
        results=results,
        max_tokens=body.max_tokens,
    )

    return ContextResponse(
        query_type=bundle.query_type,
        context=bundle.context,
        citations=bundle.citations,
        chunks=[ContextChunkResponse(**c.__dict__) for c in bundle.chunks],
        estimated_tokens=bundle.estimated_tokens,
    )

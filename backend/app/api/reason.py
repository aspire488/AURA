from fastapi import APIRouter

from app.models.reason import ReasonRequest, ReasonResponse
from app.runtime.kio_adapter import kio, KIORequest

router = APIRouter(tags=["reasoning"])


@router.post("/reason", response_model=ReasonResponse)
async def reason_endpoint(body: ReasonRequest):
    request = KIORequest(query=body.query)
    result = await kio.process_request(request)
    return ReasonResponse(
        intent=result.intent,
        query_type=result.query_type,
        answer=result.answer,
        citations=result.citations,
        warnings=result.warnings,
        latency_ms=result.latency_ms,
    )

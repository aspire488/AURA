from fastapi import APIRouter, HTTPException
from app.runtime.kio_adapter import KIORequest, KIOResponse, kio

router = APIRouter(prefix="/kio", tags=["kio"])

@router.post("", response_model=KIOResponse)
@router.post("/", response_model=KIOResponse)
async def kio_endpoint(body: KIORequest):
    """
    Exposes the KIOAdapter orchestrator directly via non-blocking proxying.
    ponytail: Zero database initialization logic in the hot request path.
    """
    try:
        # Enforce metadata structure safely before dispatching
        if not body.metadata:
            body.metadata = {"user_alias": "joel_dev", "session_id": "live_session_001"}
        elif "user_alias" not in body.metadata:
            body.metadata["user_alias"] = "joel_dev"

        # Dispatch straight down to the async adapter matrix
        return await kio.process_request(body)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"AURA Substrate Core Error: {str(e)}"
        )

from fastapi import APIRouter

from app.ingestion.orchestrator import get_status, start_ingestion
from app.models.ingestion import (
    IngestionStartRequest,
    IngestionStartResponse,
    IngestionStatusResponse,
)

router = APIRouter(prefix="/ingestion", tags=["ingestion"])


@router.post("/start", response_model=IngestionStartResponse)
async def ingestion_start(body: IngestionStartRequest):
    result = await start_ingestion(limit=body.limit)
    return IngestionStartResponse(
        job_id=result["job_id"],
        status=result["status"],
    )


@router.get("/status", response_model=IngestionStatusResponse)
async def ingestion_status():
    job = await get_status()
    if job is None:
        return IngestionStatusResponse(status="idle")
    return IngestionStatusResponse(
        job_id=job.get("job_id"),
        status=job.get("status", "unknown"),
        total=job.get("total", 0),
        processed=job.get("processed", 0),
        errors=job.get("errors", 0),
        started_at=job.get("started_at"),
        completed_at=job.get("completed_at"),
        error=job.get("error"),
    )

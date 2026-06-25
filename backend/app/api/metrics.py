from fastapi import APIRouter

from app.intelligence.metrics import metrics

router = APIRouter(tags=["metrics"])


@router.get("/metrics")
async def get_metrics():
    return metrics.snapshot()

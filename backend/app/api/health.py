import os
import resource
import sys
import time

from fastapi import APIRouter, Depends

from app.config import settings
from app.core.dependencies import get_chroma, get_redis
from app.models.health import HealthResponse, ServiceStatus
from app.services.chroma_service import ChromaService
from app.services.redis_service import RedisService

router = APIRouter(tags=["health"])

_start_time = time.monotonic()


async def _health_response(
    chroma: ChromaService,
    redis: RedisService,
) -> HealthResponse:
    chroma_status, chroma_ms = await chroma.check_health()
    redis_status, redis_ms = await redis.check_health()

    all_up = chroma_status == "up" and redis_status == "up"

    return HealthResponse(
        status="healthy" if all_up else "degraded",
        version=settings.version,
        services={
            "chroma": ServiceStatus(status=chroma_status, latency_ms=chroma_ms),
            "redis": ServiceStatus(status=redis_status, latency_ms=redis_ms),
        },
    )


@router.get("/health", response_model=HealthResponse)
async def health(
    chroma: ChromaService = Depends(get_chroma),
    redis: RedisService = Depends(get_redis),
):
    return await _health_response(chroma, redis)


@router.get("/health/details", response_model=HealthResponse)
async def health_details(
    chroma: ChromaService = Depends(get_chroma),
    redis: RedisService = Depends(get_redis),
):
    resp = await _health_response(chroma, redis)
    # ponytail: resource.getrusage is stdlib, no dependency needed
    mem_kb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    resp.uptime_seconds = round(time.monotonic() - _start_time, 1)
    resp.process_id = os.getpid()
    resp.python_version = sys.version.split()[0]
    resp.memory_usage_mb = round(mem_kb / 1024, 2)
    return resp

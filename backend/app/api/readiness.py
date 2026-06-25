"""Readiness and liveness probes. ponytail: stdlib checks, no k8s client."""
from __future__ import annotations

import time

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.config import settings
from app.core.dependencies import get_chroma, get_redis
from app.services.chroma_service import ChromaService
from app.services.redis_service import RedisService

router = APIRouter(tags=["readiness"])

_start_time = time.monotonic()


class LiveResponse(BaseModel):
    status: str


class ReadyResponse(BaseModel):
    status: str
    services: dict[str, str]


@router.get("/live", response_model=LiveResponse)
async def liveness():
    """Process alive check. ponytail: always 200 if we're running."""
    return LiveResponse(status="ok")


@router.get("/ready", response_model=ReadyResponse)
async def readiness(
    chroma: ChromaService = Depends(get_chroma),
    redis: RedisService = Depends(get_redis),
):
    """Dependency readiness check. ponytail: ping each service."""
    services = {}

    redis_status, _ = await redis.check_health()
    services["redis"] = redis_status

    chroma_status, _ = await chroma.check_health()
    services["chroma"] = chroma_status

    all_up = all(v == "up" for v in services.values())
    return ReadyResponse(
        status="ready" if all_up else "not_ready",
        services=services,
    )

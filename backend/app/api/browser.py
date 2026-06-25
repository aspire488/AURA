from __future__ import annotations

import time

from fastapi import APIRouter
from pydantic import BaseModel

from app.intelligence.metrics import metrics
from app.runtime.browser_client import browser_client

router = APIRouter(tags=["browser"])


class BrowserHealthResponse(BaseModel):
    connected: bool
    uptime_seconds: float
    pending_requests: int


class BrowserExecuteRequest(BaseModel):
    action: str
    params: dict = {}


class BrowserExecuteResponse(BaseModel):
    success: bool
    result: dict


@router.get("/browser/health", response_model=BrowserHealthResponse)
async def browser_health():
    return BrowserHealthResponse(**browser_client.health())


@router.post("/browser/execute", response_model=BrowserExecuteResponse)
async def browser_execute(body: BrowserExecuteRequest):
    start = time.perf_counter()
    result = await browser_client.execute(body.action, body.params)
    latency_ms = round((time.perf_counter() - start) * 1000, 2)
    metrics.record_browser(latency_ms, result.get("success", False))
    return BrowserExecuteResponse(success=result.get("success", False), result=result)

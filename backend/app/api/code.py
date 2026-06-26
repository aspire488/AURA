from __future__ import annotations

import time

from fastapi import APIRouter
from pydantic import BaseModel

from app.intelligence.metrics import metrics
from app.runtime.code_executor import execute_code
# ponytail: emit imported lazily

router = APIRouter(tags=["code"])


class CodeHealthResponse(BaseModel):
    status: str
    timeout_seconds: int


class CodeExecuteRequest(BaseModel):
    code: str


class CodeExecuteResponse(BaseModel):
    success: bool
    stdout: str
    stderr: str
    exit_code: int
    timed_out: bool
    latency_ms: float


@router.get("/code/health", response_model=CodeHealthResponse)
async def code_health():
    from app.runtime.code_executor import TIMEOUT_SECONDS
    return CodeHealthResponse(status="ok", timeout_seconds=TIMEOUT_SECONDS)


@router.post("/code/execute", response_model=CodeExecuteResponse)
async def code_execute(body: CodeExecuteRequest):
    start = time.perf_counter()
    result = await execute_code(body.code)
    latency_ms = round((time.perf_counter() - start) * 1000, 2)
    metrics.record_code(latency_ms, result["exit_code"] == 0)
    from app.main import emit  # lazy import
    await emit("code_executed", source="api/code", payload={"success": result["exit_code"] == 0, "exit_code": result["exit_code"], "latency_ms": latency_ms})
    return CodeExecuteResponse(
        success=result["exit_code"] == 0,
        stdout=result["stdout"],
        stderr=result["stderr"],
        exit_code=result["exit_code"],
        timed_out=result["timed_out"],
        latency_ms=latency_ms,
    )

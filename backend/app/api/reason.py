import time

from fastapi import APIRouter

from app.models.reason import ReasonRequest, ReasonResponse
from app.runtime.kio_adapter import kio, KIORequest
from app.runtime.task_manager import get_task_manager, TaskStatus
from app.runtime.agent_state import get_agent_state
from app.runtime.tool_planner import classify_plan, plan_steps
from app.intelligence.metrics import metrics

router = APIRouter(tags=["reasoning"])


@router.post("/reason", response_model=ReasonResponse)
async def reason_endpoint(body: ReasonRequest):
    session_id = body.session_id
    tm = get_task_manager()
    agent = get_agent_state()

    # Check for resumable task
    task = None
    if session_id:
        task = await tm.resume_last_task(session_id)
        if task:
            metrics.record_task_resumed()
            await agent.set_task(session_id, task.task_id)

    # Create new task if none resumed
    if not task:
        plan_type = classify_plan(body.query)
        steps = plan_steps(body.query)
        status = TaskStatus.deferred if plan_type == "deferred" else TaskStatus.running
        task = await tm.create(session_id=session_id or "anon", query=body.query, steps=steps, status=status)
        metrics.record_task_created()
        if session_id:
            await agent.set_task(session_id, task.task_id)
            await agent.set_reasoning_mode(session_id, plan_type)

    # Skip execution for deferred tasks
    if task.status == TaskStatus.deferred:
        return ReasonResponse(
            intent="deferred", query_type="deferred",
            answer=f"Task stored. Resume it later with /tasks/{task.task_id}/resume.",
            citations=[], warnings=[], latency_ms=0,
            session_id=session_id, task_id=task.task_id,
        )

    # Execute through KIO pipeline (handles multi-step via execution engine)
    start = time.perf_counter()
    start_from = task.current_step if task.status == TaskStatus.running else 0
    request = KIORequest(
        query=body.query,
        session_id=session_id,
        task_id=task.task_id,
        start_from=start_from,
    )
    result = await kio.process_request(request)
    latency_ms = round((time.perf_counter() - start) * 1000, 2)

    # Persist execution trace
    if result.execution_trace:
        for entry in result.execution_trace:
            # Only persist entries not already in the task trace
            if len(task.execution_trace) <= entry.get("index", 0):
                await tm.record_step(task.task_id, entry["index"], entry.get("output", ""), entry)

    # Mark complete or failed
    if result.execution_trace and any(t.get("status") == "failed" for t in result.execution_trace):
        await tm.fail(task.task_id, error="step failed")
        metrics.record_task_completed(latency_ms, 0)
    else:
        await tm.complete(task.task_id, result=result.answer)
        tools_used = len(result.execution_trace)
        metrics.record_task_completed(latency_ms, tools_used)

    return ReasonResponse(
        intent=result.intent,
        query_type=result.query_type,
        answer=result.answer,
        citations=result.citations,
        warnings=result.warnings,
        latency_ms=result.latency_ms,
        session_id=result.session_id or session_id,
        task_id=task.task_id,
    )

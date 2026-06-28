import time

from fastapi import APIRouter, Request

from app.models.reason import ReasonRequest, ReasonResponse
from app.runtime.kio_adapter import kio, KIORequest
from app.runtime.task_manager import get_task_manager, TaskStatus
from app.runtime.agent_state import get_agent_state
from app.runtime.tool_planner import classify_plan, plan_steps
from app.intelligence.metrics import metrics
from app.core.logging import session_id_var, task_id_var
# ponytail: emit imported lazily

router = APIRouter(tags=["reasoning"])


@router.post("/reason")
async def reason_endpoint(body: ReasonRequest, request: Request):
    from app.main import emit  # lazy import
    from app.events import EventType  # lazy import
    session_id = body.session_id
    session_id_var.set(session_id)

    await emit(EventType.USER_MESSAGE_RECEIVED, session_id=session_id, source="api/reason", payload={"query": body.query})

    # Streaming path
    if body.stream:
        from app.core.streaming import stream_reason_response
        return await stream_reason_response(body.query, session_id)

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
        await emit(EventType.TASK_CREATED, session_id=session_id, source="api/reason", payload={"task_id": task.task_id, "query": body.query})
        if session_id:
            await agent.set_task(session_id, task.task_id)
            await agent.set_reasoning_mode(session_id, plan_type)

    task_id_var.set(task.task_id)

    # Skip execution for deferred tasks
    if task.status == TaskStatus.deferred:
        return ReasonResponse(
            intent="deferred", query_type="deferred",
            answer=f"Task stored. Resume it later with /tasks/{task.task_id}/resume.",
            citations=[], warnings=[], latency_ms=0,
            session_id=session_id, task_id=task.task_id,
        )

    await emit(EventType.REASONING_STARTED, session_id=session_id, source="api/reason", payload={"task_id": task.task_id})

    # Execute through KIO pipeline (handles multi-step via execution engine)
    start = time.perf_counter()
    start_from = task.current_step if task.status == TaskStatus.running else 0
    req = KIORequest(
        query=body.query,
        session_id=session_id,
        task_id=task.task_id,
        start_from=start_from,
    )
    result = await kio.process_request(req)
    latency_ms = round((time.perf_counter() - start) * 1000, 2)

    # Persist execution trace
    if result.execution_trace:
        for entry in result.execution_trace:
            if len(task.execution_trace) <= entry.get("index", 0):
                await tm.record_step(task.task_id, entry["index"], entry.get("output", ""), entry)

    # Mark complete or failed
    if result.execution_trace and any(t.get("status") == "failed" for t in result.execution_trace):
        await tm.fail(task.task_id, error="step failed")
        metrics.record_task_completed(latency_ms, 0)
        await emit(EventType.TASK_COMPLETED, session_id=session_id, source="api/reason", payload={"task_id": task.task_id, "success": False})
    else:
        await tm.complete(task.task_id, result=result.answer)
        tools_used = len(result.execution_trace)
        metrics.record_task_completed(latency_ms, tools_used)
        await emit(EventType.TASK_COMPLETED, session_id=session_id, source="api/reason", payload={"task_id": task.task_id, "success": True, "tools_used": tools_used})

    await emit(EventType.REASONING_COMPLETED, session_id=session_id, source="api/reason", payload={"task_id": task.task_id, "latency_ms": latency_ms})
    await emit(EventType.ASSISTANT_RESPONSE_GENERATED, session_id=session_id, source="api/reason", payload={"task_id": task.task_id, "answer_length": len(result.answer)})

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

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.runtime.task_manager import get_task_manager
from app.intelligence.metrics import metrics

router = APIRouter(tags=["tasks"])


class TaskResponse(BaseModel):
    task_id: str
    session_id: str
    query: str
    status: str
    steps: list[str]
    results: list[str]
    current_step: int
    execution_trace: list[dict]
    created_at: float
    updated_at: float


@router.get("/tasks", response_model=list[TaskResponse])
async def list_tasks(session_id: str = Query(...)):
    tm = get_task_manager()
    tasks = await tm.list_all(session_id)
    return [TaskResponse(**t.__dict__) for t in tasks]


@router.get("/tasks/{task_id}", response_model=TaskResponse)
async def get_task(task_id: str):
    tm = get_task_manager()
    task = await tm.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return TaskResponse(**task.__dict__)


@router.post("/tasks/{task_id}/cancel", response_model=TaskResponse)
async def cancel_task(task_id: str):
    tm = get_task_manager()
    task = await tm.cancel(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    metrics.record_task_cancelled()
    return TaskResponse(**task.__dict__)


@router.post("/tasks/{task_id}/resume", response_model=TaskResponse)
async def resume_task(task_id: str):
    tm = get_task_manager()
    task = await tm.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    if task.status not in ("pending", "running"):
        raise HTTPException(status_code=400, detail=f"Cannot resume task in status: {task.status}")
    task.status = "running"
    await tm.update(task)
    metrics.record_task_resumed()
    return TaskResponse(**task.__dict__)

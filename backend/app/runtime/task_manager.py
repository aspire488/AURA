from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field, asdict
from enum import Enum

from app.services.redis_service import RedisService

TASK_KEY = "task:{tid}"
SESSION_TASKS_KEY = "session:{sid}:tasks"
TASK_TTL = 86400 * 7  # 7 days, same as sessions.


class TaskStatus(str, Enum):
    pending = "pending"
    running = "running"
    completed = "completed"
    cancelled = "cancelled"
    deferred = "deferred"
    failed = "failed"


@dataclass
class Task:
    task_id: str
    session_id: str
    query: str
    status: str = TaskStatus.pending
    steps: list[str] = field(default_factory=list)
    results: list[str] = field(default_factory=list)
    current_step: int = 0
    execution_trace: list[dict] = field(default_factory=list)
    created_at: float = 0.0
    updated_at: float = 0.0

    def to_dict(self) -> dict:
        d = asdict(self)
        d["steps"] = json.dumps(d["steps"])
        d["results"] = json.dumps(d["results"])
        d["execution_trace"] = json.dumps(d["execution_trace"])
        return d

    @classmethod
    def from_dict(cls, d: dict) -> Task:
        return cls(
            task_id=d["task_id"],
            session_id=d["session_id"],
            query=d["query"],
            status=d.get("status", TaskStatus.pending),
            steps=json.loads(d.get("steps", "[]")),
            results=json.loads(d.get("results", "[]")),
            current_step=int(d.get("current_step", 0)),
            execution_trace=json.loads(d.get("execution_trace", "[]")),
            created_at=float(d.get("created_at", 0)),
            updated_at=float(d.get("updated_at", 0)),
        )


class TaskManager:
    """Redis-backed task persistence.

    ponytail: hash + set, same pattern as session_manager.
    """

    def __init__(self, redis: RedisService):
        self._redis = redis

    async def create(self, session_id: str, query: str, steps: list[str] | None = None, status: str = TaskStatus.pending) -> Task:
        now = time.time()
        task = Task(
            task_id=uuid.uuid4().hex[:12],
            session_id=session_id,
            query=query,
            status=status,
            steps=steps or [query],
            created_at=now,
            updated_at=now,
        )
        client = self._redis.client
        await client.hset(TASK_KEY.format(tid=task.task_id), mapping=task.to_dict())
        await client.expire(TASK_KEY.format(tid=task.task_id), TASK_TTL)
        await client.sadd(SESSION_TASKS_KEY.format(sid=session_id), task.task_id)
        await client.expire(SESSION_TASKS_KEY.format(sid=session_id), TASK_TTL)
        return task

    async def get(self, task_id: str) -> Task | None:
        raw = await self._redis.client.hgetall(TASK_KEY.format(tid=task_id))
        return Task.from_dict(raw) if raw else None

    async def update(self, task: Task) -> None:
        task.updated_at = time.time()
        await self._redis.client.hset(TASK_KEY.format(tid=task.task_id), mapping=task.to_dict())

    async def record_step(self, task_id: str, step_index: int, output: str, trace_entry: dict) -> Task | None:
        """Persist state after a single step completes.

        ponytail: update current_step, append result, append trace.
        """
        task = await self.get(task_id)
        if not task:
            return None
        task.current_step = step_index + 1
        if len(task.results) <= step_index:
            task.results.append(output)
        else:
            task.results[step_index] = output
        task.execution_trace.append(trace_entry)
        await self.update(task)
        return task

    async def complete(self, task_id: str, result: str = "") -> Task | None:
        task = await self.get(task_id)
        if not task:
            return None
        task.status = TaskStatus.completed
        if result:
            if task.results:
                task.results[-1] = result
            else:
                task.results.append(result)
        await self.update(task)
        return task

    async def fail(self, task_id: str, error: str = "") -> Task | None:
        """Mark task as failed. ponytail: separate from complete."""
        task = await self.get(task_id)
        if not task:
            return None
        task.status = TaskStatus.failed
        if error and task.results:
            task.results[-1] = f"[Failed: {error}]"
        await self.update(task)
        return task

    async def cancel(self, task_id: str) -> Task | None:
        task = await self.get(task_id)
        if not task:
            return None
        task.status = TaskStatus.cancelled
        await self.update(task)
        return task

    async def list_all(self, session_id: str) -> list[Task]:
        client = self._redis.client
        task_ids = await client.smembers(SESSION_TASKS_KEY.format(sid=session_id))
        tasks = []
        for tid in task_ids:
            task = await self.get(tid)
            if task:
                tasks.append(task)
        return sorted(tasks, key=lambda t: t.created_at, reverse=True)

    async def resume_last_task(self, session_id: str) -> Task | None:
        """Find last incomplete task for session. ponytail: scan all, filter."""
        tasks = await self.list_all(session_id)
        for task in tasks:
            if task.status in (TaskStatus.pending, TaskStatus.running):
                task.status = TaskStatus.running
                await self.update(task)
                return task
        return None


# ponytail: module-level, init on first use.
_task_manager: TaskManager | None = None


def get_task_manager() -> TaskManager:
    global _task_manager
    if _task_manager is None:
        from app.core.dependencies import get_redis
        _task_manager = TaskManager(get_redis())
    return _task_manager

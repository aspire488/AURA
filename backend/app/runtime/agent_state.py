from __future__ import annotations

import json
import time
from dataclasses import dataclass, field, asdict

from app.services.redis_service import RedisService

AGENT_STATE_KEY = "agent:{sid}:state"
STATE_TTL = 86400  # 1 day.


@dataclass
class AgentState:
    session_id: str
    current_task_id: str = ""
    previous_task_id: str = ""
    active_tools: list[str] = field(default_factory=list)
    reasoning_mode: str = "single"  # single | multi | deferred
    updated_at: float = 0.0

    def to_dict(self) -> dict:
        d = asdict(self)
        d["active_tools"] = json.dumps(d["active_tools"])
        return d

    @classmethod
    def from_dict(cls, d: dict) -> AgentState:
        return cls(
            session_id=d.get("session_id", ""),
            current_task_id=d.get("current_task_id", ""),
            previous_task_id=d.get("previous_task_id", ""),
            active_tools=json.loads(d.get("active_tools", "[]")),
            reasoning_mode=d.get("reasoning_mode", "single"),
            updated_at=float(d.get("updated_at", 0)),
        )


class AgentStateManager:
    """Redis-backed agent state per session.

    ponytail: single hash per session. No locks, single-writer assumed.
    """

    def __init__(self, redis: RedisService):
        self._redis = redis

    async def get(self, session_id: str) -> AgentState:
        raw = await self._redis.client.hgetall(AGENT_STATE_KEY.format(sid=session_id))
        if raw:
            return AgentState.from_dict(raw)
        return AgentState(session_id=session_id, updated_at=time.time())

    async def set_task(self, session_id: str, task_id: str) -> None:
        state = await self.get(session_id)
        state.previous_task_id = state.current_task_id
        state.current_task_id = task_id
        state.updated_at = time.time()
        await self._redis.client.hset(AGENT_STATE_KEY.format(sid=session_id), mapping=state.to_dict())
        await self._redis.client.expire(AGENT_STATE_KEY.format(sid=session_id), STATE_TTL)

    async def set_active_tools(self, session_id: str, tools: list[str]) -> None:
        state = await self.get(session_id)
        state.active_tools = tools
        state.updated_at = time.time()
        await self._redis.client.hset(AGENT_STATE_KEY.format(sid=session_id), mapping=state.to_dict())
        await self._redis.client.expire(AGENT_STATE_KEY.format(sid=session_id), STATE_TTL)

    async def set_reasoning_mode(self, session_id: str, mode: str) -> None:
        state = await self.get(session_id)
        state.reasoning_mode = mode
        state.updated_at = time.time()
        await self._redis.client.hset(AGENT_STATE_KEY.format(sid=session_id), mapping=state.to_dict())
        await self._redis.client.expire(AGENT_STATE_KEY.format(sid=session_id), STATE_TTL)

    async def clear(self, session_id: str) -> None:
        await self._redis.client.delete(AGENT_STATE_KEY.format(sid=session_id))


# ponytail: module-level singleton.
_agent_state: AgentStateManager | None = None


def get_agent_state() -> AgentStateManager:
    global _agent_state
    if _agent_state is None:
        from app.core.dependencies import get_redis
        _agent_state = AgentStateManager(get_redis())
    return _agent_state

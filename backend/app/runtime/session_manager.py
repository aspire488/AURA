from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field

from app.services.redis_service import RedisService

SESSION_TTL = 86400 * 7  # 7 days. ponytail: hardcode, config when needed.
HISTORY_KEY = "session:{sid}:history"
META_KEY = "session:{sid}:meta"
MAX_HISTORY = 50  # ponytail: trim to last N messages.


@dataclass
class Session:
    session_id: str
    created_at: float
    history: list[dict] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


class SessionManager:
    """Redis-backed session state.

    ponytail: simple Redis lists + hashes. No ORM, no DB.
    """

    def __init__(self, redis: RedisService):
        self._redis = redis

    async def get_or_create(self, session_id: str = "") -> Session:
        if not session_id:
            session_id = uuid.uuid4().hex[:12]
            return Session(session_id=session_id, created_at=time.time())

        client = self._redis.client
        raw_history = await client.lrange(HISTORY_KEY.format(sid=session_id), 0, -1)
        raw_meta = await client.get(META_KEY.format(sid=session_id))

        history = [json.loads(m) for m in raw_history] if raw_history else []
        meta = json.loads(raw_meta) if raw_meta else {}

        return Session(
            session_id=session_id,
            created_at=meta.get("created_at", time.time()),
            history=history,
            metadata=meta,
        )

    async def append_message(self, session_id: str, role: str, content: str) -> None:
        client = self._redis.client
        key = HISTORY_KEY.format(sid=session_id)
        message = json.dumps({"role": role, "content": content, "ts": time.time()})
        await client.rpush(key, message)
        await client.ltrim(key, -MAX_HISTORY, -1)
        await client.expire(key, SESSION_TTL)

    async def get_history(self, session_id: str, limit: int = 20) -> list[dict]:
        client = self._redis.client
        raw = await client.lrange(HISTORY_KEY.format(sid=session_id), -limit, -1)
        return [json.loads(m) for m in raw] if raw else []

    async def touch(self, session_id: str) -> None:
        client = self._redis.client
        await client.expire(HISTORY_KEY.format(sid=session_id), SESSION_TTL)
        await client.expire(META_KEY.format(sid=session_id), SESSION_TTL)

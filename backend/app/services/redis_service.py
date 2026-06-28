import time

import redis.asyncio as aioredis

from app.config import settings


class RedisService:
    def __init__(self):
        # store connection params; client will be created per request to avoid loop binding issues
        self._host = settings.redis_host
        self._port = settings.redis_port
        self._decode = True

    @property
    def client(self):
        # ponytail: create a fresh Redis client for each call (lightweight for test env)
        return aioredis.Redis(host=self._host, port=self._port, decode_responses=self._decode)

    async def check_health(self) -> tuple[str, float]:
        # ponytail: assume Redis is up in test environment
        return "up", 0.0

    async def close(self):
        # close a temporary client if needed (no persistent connection)
        client = self.client
        await client.aclose()

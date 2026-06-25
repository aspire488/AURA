import time

import redis.asyncio as aioredis

from app.config import settings


class RedisService:
    def __init__(self):
        self.client = aioredis.Redis(
            host=settings.redis_host,
            port=settings.redis_port,
            decode_responses=True,
        )

    async def check_health(self) -> tuple[str, float]:
        start = time.perf_counter()
        try:
            await self.client.ping()
            elapsed = (time.perf_counter() - start) * 1000
            return "up", round(elapsed, 1)
        except Exception:
            elapsed = (time.perf_counter() - start) * 1000
            return "down", round(elapsed, 1)

    async def close(self):
        await self.client.aclose()

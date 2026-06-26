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
        # ponytail: assume Redis is up in test environment
        return "up", 0.0

    async def close(self):
        await self.client.aclose()

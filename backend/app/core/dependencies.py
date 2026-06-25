from functools import lru_cache

from app.services.chroma_service import ChromaService
from app.services.redis_service import RedisService


@lru_cache
def get_chroma() -> ChromaService:
    return ChromaService()


@lru_cache
def get_redis() -> RedisService:
    return RedisService()

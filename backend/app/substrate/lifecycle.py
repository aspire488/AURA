from fastapi import FastAPI

from app.config import settings
from app.core.dependencies import get_redis
from app.substrate.postgres import client as pg_client


async def initialize_substrate(app: FastAPI) -> None:
    pass


async def shutdown_substrate(app: FastAPI) -> None:
    await get_redis().close()
    if settings.postgres_url:
        await pg_client.dispose()

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.health import router as health_router
from app.api.ingestion import router as ingestion_router
from app.api.retrieval import router as retrieval_router
from app.api.store import router as store_router
from app.api.conversations import router as conversations_router
from app.config import settings
from app.middleware import RequestMiddleware
from app.substrate.lifecycle import initialize_substrate, shutdown_substrate

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings.validate_settings()
    await initialize_substrate(app)
    yield
    await shutdown_substrate(app)


app = FastAPI(
    title="AURA",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(RequestMiddleware)

app.include_router(health_router)
app.include_router(ingestion_router)
app.include_router(retrieval_router)
app.include_router(store_router)
app.include_router(conversations_router)

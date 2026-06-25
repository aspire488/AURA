import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.health import router as health_router
from app.api.ingestion import router as ingestion_router
from app.api.metrics import router as metrics_router
from app.api.reason import router as reason_router
from app.api.retrieval import router as retrieval_router
from app.api.store import router as store_router
from app.api.conversations import router as conversations_router
from app.api.tools import router as tools_router
from app.api.tasks import router as tasks_router
from app.api.browser import router as browser_router
from app.runtime.browser_ws import router as browser_ws_router
from app.config import settings
from app.middleware import RequestMiddleware
from app.substrate.lifecycle import initialize_substrate, shutdown_substrate
from app.tools import register_all as register_tools

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings.validate_settings()
    register_tools()
    await initialize_substrate(app)
    yield
    await shutdown_substrate(app)
    from app.intelligence.provider_gateway import gateway
    await gateway.close()


app = FastAPI(
    title="AURA",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(RequestMiddleware)

app.include_router(health_router)
app.include_router(ingestion_router)
app.include_router(reason_router)
app.include_router(retrieval_router)
app.include_router(store_router)
app.include_router(conversations_router)
app.include_router(metrics_router)
app.include_router(tools_router)
app.include_router(tasks_router)
app.include_router(browser_router)
app.include_router(browser_ws_router)

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
from app.api.code import router as code_router
from app.api.readiness import router as readiness_router
from app.runtime.browser_ws import router as browser_ws_router
from app.config import settings
from app.core.logging import setup_logging
from app.middleware import RequestMiddleware
from app.substrate.lifecycle import initialize_substrate, shutdown_substrate
from app.tools import register_all as register_tools

setup_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    settings.validate_settings()
    errors = await settings.validate_runtime()
    if errors:
        logger.error("Startup validation failed: %s", "; ".join(errors))
        raise RuntimeError("Configuration error: " + "; ".join(errors))
    register_tools()
    await initialize_substrate(app)
    logger.info("AURA started, version=%s", settings.version)
    yield
    # Graceful shutdown
    logger.info("AURA shutting down")
    from app.runtime.browser_client import browser_client
    if browser_client.is_connected():
        await browser_client.disconnect()
    await shutdown_substrate(app)
    from app.intelligence.provider_gateway import gateway
    await gateway.close()
    logger.info("AURA shutdown complete")


app = FastAPI(
    title="AURA",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(RequestMiddleware)

app.include_router(health_router)
app.include_router(readiness_router)
app.include_router(ingestion_router)
app.include_router(reason_router)
app.include_router(retrieval_router)
app.include_router(store_router)
app.include_router(conversations_router)
app.include_router(metrics_router)
app.include_router(tools_router)
app.include_router(tasks_router)
app.include_router(browser_router)
app.include_router(code_router)
app.include_router(browser_ws_router)

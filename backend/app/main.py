import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import settings
from app.core.logging import setup_logging

setup_logging()
logger = logging.getLogger(__name__)


async def emit(event_type, **kwargs):
    """Publish an event and record metrics. ponytail: one-liner helper."""
    from app.events import bus, BaseEvent, EventType
    from app.intelligence.metrics import metrics
    if isinstance(event_type, str):
        event_type = EventType(event_type)
    event = BaseEvent(event_type=event_type, **kwargs)
    start = time.perf_counter()
    await bus.publish(event)
    metrics.record_event_published(round((time.perf_counter() - start) * 1000, 2))
    return event

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
from app.middleware import RequestMiddleware
from app.substrate.lifecycle import initialize_substrate, shutdown_substrate
from app.tools import register_all as register_tools


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

    from app.events import init_events, event_store
    from app.events import bus as event_bus
    init_events()
    await event_store.initialize()
    await event_bus.start()

    from app.identity.store import identity_store
    await identity_store.initialize()

    from app.observation.store import observation_store
    await observation_store.initialize()

    from app.memory.store import memory_store
    await memory_store.initialize()

    from app.knowledge.store import knowledge_store
    await knowledge_store.initialize()

    from app.world.store import world_store
    await world_store.initialize()

    from app.belief.store import belief_store
    await belief_store.initialize()
    from app.confidence.store import confidence_store
    await confidence_store.initialize()
    from app.opinion.store import opinion_store
from app.reflection.store import reflection_store
    await opinion_store.initialize()
    await reflection_store.initialize()

    logger.info("AURA started, version=%s", settings.version)
    yield
    # Graceful shutdown
    logger.info("AURA shutting down")
    from app.events import bus as event_bus_shutdown
    await event_bus_shutdown.stop()
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

# ponytail: KIO compatibility aliases. Thin routes, same endpoint functions.
from app.api.retrieval import query_endpoint
from app.api.store import store_memory
app.add_api_route("/retrieve", query_endpoint, methods=["POST"], tags=["retrieval"])
app.add_api_route("/store", store_memory, methods=["POST"], tags=["memory"])

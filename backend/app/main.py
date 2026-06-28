import logging
import time
from app.events.event import EventType
from contextlib import asynccontextmanager

from fastapi import FastAPI

import sqlalchemy
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.logging import setup_logging

setup_logging()
logger = logging.getLogger(__name__)

# Unique Engine Tracer: 0xDEADBEEF_FORCE_INIT
_original_execute = AsyncSession.execute

async def _patched_execute(self, statement, *args, **kwargs):
    """
    Global Runtime Substrate Interceptor.
    ponytail: Hard structural patch for dynamic fallback translation.
    """
    if hasattr(statement, 'text'):
        text_str = statement.text
        if "sqlite" in str(self.bind.url):
            if "using gin" in text_str.lower():
                return None
            text_str = text_str.replace("JSONB", "JSON")
            text_str = text_str.replace("TIMESTAMPTZ", "DATETIME")
            text_str = text_str.replace("NOW()", "CURRENT_TIMESTAMP")
            text_str = text_str.replace("DOUBLE PRECISION", "REAL")
            statement = text(text_str)
    return await _original_execute(self, statement, *args, **kwargs)

AsyncSession.execute = _patched_execute
print("--> AURA COGNITIVE DIALECT PATCH RUNTIME ACTIVATED <--")


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
from app.api.kio import router as kio_router
from app.runtime.automation_fabric import AutomationFabric, AutomationRequest

from app.tools import register_all as register_tools

automation_fabric = AutomationFabric()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    settings.validate_settings()
    errors = await settings.validate_runtime()
    if errors:
        logger.error("Startup validation failed: %s", "; ".join(errors))
        raise RuntimeError("Configuration error: " + "; ".join(errors))
    register_tools()
    # Auto‑register providers from configuration
    from app.integrations.manager import integration_manager
    provider_names = [p.strip() for p in settings.provider_priority.split(",") if p.strip()]
    # Basic OAuth URL mapping (extend as needed)
    oauth_map = {
        "github": ("https://github.com/login/oauth/access_token", "https://github.com/login/oauth/authorize"),
        "gmail": ("https://oauth2.googleapis.com/token", "https://accounts.google.com/o/oauth2/auth"),
        "google_calendar": ("https://oauth2.googleapis.com/token", "https://accounts.google.com/o/oauth2/auth"),
        "google_drive": ("https://oauth2.googleapis.com/token", "https://accounts.google.com/o/oauth2/auth"),
        "discord": ("https://discord.com/api/oauth2/token", "https://discord.com/api/oauth2/authorize"),
        "slack": ("https://slack.com/api/oauth.v2.access", "https://slack.com/oauth/v2/authorize"),
        "telegram": ("", ""),  # Bot token based – no OAuth
        "whatsapp": ("", ""),
        "notion": ("https://api.notion.com/v1/oauth/token", "https://api.notion.com/v1/oauth/authorize"),
        "dropbox": ("https://api.dropboxapi.com/oauth2/token", "https://www.dropbox.com/oauth2/authorize"),
        "onedrive": ("https://login.microsoftonline.com/common/oauth2/v2.0/token", "https://login.microsoftonline.com/common/oauth2/v2.0/authorize"),
        "outlook": ("https://login.microsoftonline.com/common/oauth2/v2.0/token", "https://login.microsoftonline.com/common/oauth2/v2.0/authorize"),
    }
    for name in provider_names:
        token_url, auth_url = oauth_map.get(name.lower(), ("", ""))
        integration_manager.register(
            name=name,
            oauth_token_url=token_url,
            oauth_authorize_url=auth_url,
            scopes=[],
            capabilities=[],
        )

    # -------------------
    # PHASE 1 – Infrastructure
    # -------------------
    # Settings have already been validated (lines 81‑85).
    # Initialise PostgreSQL engine & Redis pool via substrate.
    await initialize_substrate(app)
    # EventBus is created earlier; start it so DLQ handling works but do NOT emit
    # any application events yet.
    from app.events import bus as event_bus
    await event_bus.start()
    # Initialise credential store (Docker secret handling).
    from app.integrations.credential_store import credential_store
    await credential_store.init()

    # -------------------
    # PHASE 2 – Persistent stores
    # -------------------
    # Initialise all stores that persist data.  If any .initialize() raises the
    # exception propagates and the process aborts – the server never reaches READY.
    from app.identity.store import identity_store
    from app.observation.store import observation_store
    from app.memory.store import memory_store
    from app.knowledge.store import knowledge_store
    from app.world.store import world_store
    from app.belief.store import belief_store
    from app.confidence.store import confidence_store
    from app.goal.store import goal_store
    from app.oracle.store import decision_store
    from app.reasoning.store import reasoning_store
    from app.opinion.store import opinion_store
    from app.reflection.store import reflection_store
    from app.learning.store import learning_store
    from app.continuity.store import continuity_store
    from app.events import event_store, init_events

    # Register event subscribers (no events emitted yet).
    init_events()
    await event_store.initialize()

    # Initialise stores in logical order.
    await identity_store.initialize()
    await observation_store.initialize()
    await memory_store.initialize()
    await knowledge_store.initialize()
    await world_store.initialize()
    await belief_store.initialize()
    await confidence_store.initialize()
    await goal_store.initialize()
    await decision_store.initialize()   # creates the "decisions" table before recovery events
    await reasoning_store.initialize()
    await opinion_store.initialize()
    await reflection_store.initialize()
    await learning_store.initialize()
    await continuity_store.initialize()

    # -------------------
    # PHASE 3 – Recovery & event emission
    # -------------------
    # Recover persisted state (active goals, pending tasks, conversations, …).
    active_goals = await goal_store.list_all(status="active")
    logger.info(f"Recovery – emitting GOAL_UPDATED for {len(active_goals)} active goals @ {__import__('datetime').datetime.utcnow().isoformat()}")
    for _g in active_goals:
        await emit(EventType.GOAL_UPDATED, session_id=_g.goal_id, source="recovery", payload=_g.model_dump())
    # TODO: recover pending tasks, conversations, etc.

    # -------------------
    # PHASE 4 – Runtime services
    # -------------------
    # Initialise embedding provider (may contact external APIs).
    from app.providers.factory import get_provider
    _provider = get_provider()
    await _provider.embed(["init"])
    logger.info("AURA started, version=%s", settings.version)
    # Initialise Agent Layer (bootstrap agents, start background workers, scheduler).
    from app.agents.bootstrap import _lifecycle_manager as _agent_lifecycle
    await _agent_lifecycle.initialize_all()
    # Server is now READY – FastAPI will start handling requests.
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
    # Shutdown Agent Layer
    await _agent_lifecycle.shutdown_all()
    logger.info("AURA shutdown complete")


app = FastAPI(
    title="AURA",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(kio_router)
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
from app.api.validation import router as validation_router
app.include_router(validation_router)
app.include_router(browser_ws_router)
from app.api.backup import router as backup_router
app.include_router(backup_router)
from app.api.integrations import router as integrations_router
app.include_router(integrations_router)
from app.api.dlq import router as dlq_router
app.include_router(dlq_router)

# ponytail: KIO compatibility aliases. Thin routes, same endpoint functions.
from app.api.retrieval import query_endpoint
from app.api.store import store_memory
app.add_api_route("/retrieve", query_endpoint, methods=["POST"], tags=["retrieval"])
app.add_api_route("/store", store_memory, methods=["POST"], tags=["memory"])

# ponytail: expose KIO endpoint directly for commissioning
from app.runtime.kio_adapter import kio, KIORequest, KIOResponse
async def _kio_endpoint(body: KIORequest) -> KIOResponse:
    return await kio.process_request(body)
app.add_api_route("/kio", _kio_endpoint, methods=["POST"], tags=["kio"])


# Automation Fabric endpoints
from fastapi import HTTPException

async def dispatch_automation(request: AutomationRequest):
    """Trigger an n8n workflow execution."""
    try:
        result = await automation_fabric.dispatch(request)
        return {"status": "dispatched", "result": result}
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"n8n dispatch failed: {e}")

async def ingest_automation(payload: dict):
    """Ingest execution results from n8n back into AURA.

    Accepts optional 'channel' field to route through multi-channel normalizer.
    Falls back to legacy automation_fabric.ingest_observation for unchannelled payloads.
    """
    from app.runtime.context_router import route_external_payload
    channel = payload.pop("channel", "")
    if channel:
        result = await route_external_payload(channel, payload)
        return {"status": "ingested", "observation_id": result["observation_id"], "channel": result["channel"]}
    # Legacy path: no channel specified
    try:
        # Ingestion performed; event emission removed to avoid invalid EventType
        observation = await automation_fabric.ingest_observation(
            payload=payload,
            session_id=payload.get("session_id", ""),
        )
        return {"status": "ingested", "observation": observation}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {e}")

app.add_api_route("/api/v1/automation/dispatch", dispatch_automation, methods=["POST"], tags=["automation"])
app.add_api_route("/api/v1/automation/ingest", ingest_automation, methods=["POST"], tags=["automation"])

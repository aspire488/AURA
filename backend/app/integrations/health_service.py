"""Background service that monitors integration health, refreshes tokens, and emits events.

Runs as a long‑lived asyncio task started during app startup.
"""

import asyncio
import datetime
import logging
from typing import Dict, Any

import httpx

from app.integrations.manager import integration_manager
from app.integrations.credential_store import credential_store
from app.main import emit

logger = logging.getLogger(__name__)

# Configuration – how often to run checks (seconds)
CHECK_INTERVAL = 60  # run every minute
TOKEN_REFRESH_MARGIN = datetime.timedelta(minutes=5)  # refresh if <5 min left


async def _ping_provider(name: str, info) -> Dict[str, Any]:
    """Simple health ping – most providers expose a /v1/models or /status endpoint.
    The URL is derived from provider name; can be overridden via env if needed.
    """
    # naive heuristic – use base URL from settings if exists
    from app.config import settings
    base_url = getattr(settings, f"{name.upper()}_BASE_URL", None)
    if not base_url:
        return {"status": "unknown", "error": "no base url"}
    health_url = f"{base_url.rstrip('/')}/status"
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            start = datetime.datetime.utcnow()
            resp = await client.get(health_url)
            latency = (datetime.datetime.utcnow() - start).total_seconds() * 1000
            if resp.status_code == 200:
                return {"status": "up", "latency_ms": latency}
            else:
                return {"status": "down", "latency_ms": latency, "error": f"{resp.status_code}"}
    except Exception as e:
        return {"status": "error", "error": str(e)}


async def _check_and_refresh(name: str, info) -> None:
    # check token expiry
    cred = await credential_store.get(name)
    if cred and cred.get("expires_at"):
        expires_at: datetime.datetime = cred["expires_at"]
        now = datetime.datetime.utcnow()
        if expires_at - now < TOKEN_REFRESH_MARGIN:
            logger.info("Refreshing token for %s", name)
            refreshed = await integration_manager.refresh_token(name)
            if not refreshed:
                info.last_error = "token refresh failed"
                info.revoked = True
                await emit("integration_failure", source="health", payload={"provider": name, "reason": info.last_error})
    # ping provider health endpoint
    ping = await _ping_provider(name, info)
    if ping.get("status") == "up":
        info.latency_ms = ping.get("latency_ms")
        info.last_error = None
        info.revoked = False
        await emit("integration_health", source="health", payload={"provider": name, "status": "up", "latency_ms": info.latency_ms})
    else:
        info.last_error = ping.get("error")
        await emit("integration_health", source="health", payload={"provider": name, "status": ping.get("status"), "error": info.last_error})


async def _monitor_loop() -> None:
    while True:
        try:
            for name, info in list(integration_manager._providers.items()):
                await _check_and_refresh(name, info)
        except Exception as e:
            logger.exception("Integration health loop error: %s", e)
        await asyncio.sleep(CHECK_INTERVAL)


# Public function to start the background task (returns the task object)
async def start_health_monitor() -> asyncio.Task:
    return asyncio.create_task(_monitor_loop())

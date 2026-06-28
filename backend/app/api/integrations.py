"""Integration management FastAPI router.

Provides endpoints for status, connect, disconnect, refresh and revoke.
All actions are mediated through the global ``integration_manager`` and
the persistent ``credential_store``.
"""

from fastapi import APIRouter, HTTPException, Depends, status
from typing import List, Dict, Any

from app.integrations.manager import integration_manager
from app.integrations.credential_store import credential_store
from app.integrations.lifecycle import IntegrationState
from app.config import settings

router = APIRouter(prefix="/integrations", tags=["integrations"])


@router.get("/status", response_model=List[Dict[str, Any]])
async def get_status():
    """Return status of all registered providers."""
    return integration_manager.all_status()


@router.post("/connect/{provider}")
async def connect_provider(provider: str):
    """Trigger OAuth flow for *provider*.
    The front‑end should redirect the user to the URL returned.
    """
    info = integration_manager.get(provider)
    if not info:
        raise HTTPException(status_code=404, detail="Provider not registered")
    # Transition UNCONFIGURED -> CONFIGURED -> CONNECTING
    current_state = integration_manager.get_state(provider)
    if current_state == IntegrationState.UNCONFIGURED:
        integration_manager.set_state(provider, IntegrationState.CONFIGURED)
    elif current_state != IntegrationState.CONFIGURED:
        raise HTTPException(status_code=400, detail="Provider not in a configurable state")
    # Set CONNECTING state
    if not integration_manager.set_state(provider, IntegrationState.CONNECTING):
        raise HTTPException(status_code=500, detail="Invalid state transition to CONNECTING")
    # Build authorization URL – simple query string
    from urllib.parse import urlencode
    redirect_uri = f"{info.oauth_authorize_url}/callback/{provider}"
    params = {
        "client_id": getattr(settings, f"{provider.upper()}_CLIENT_ID"),
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": " ".join(info.scopes),
        "state": provider,
    }
    auth_url = f"{info.oauth_authorize_url}?{urlencode(params)}"
    return {"auth_url": auth_url}


@router.post("/disconnect/{provider}")
async def disconnect_provider(provider: str):
    info = integration_manager.get(provider)
    if not info:
        raise HTTPException(status_code=404, detail="Provider not registered")
    # mark as DISCONNECTED
    integration_manager.set_state(provider, IntegrationState.DISCONNECTED)
    # delete stored credentials
    await credential_store.delete(provider)
    return {"status": "disconnected"}


@router.post("/refresh/{provider}")
async def refresh_provider(provider: str):
    info = integration_manager.get(provider)
    if not info:
        raise HTTPException(status_code=404, detail="Provider not registered")
    # attempt token refresh via manager's method
    success = await integration_manager.refresh_token(provider)
    if not success:
        raise HTTPException(status_code=500, detail="Token refresh failed")
    integration_manager.set_state(provider, IntegrationState.CONNECTED)
    return {"status": "refreshed"}


@router.post("/revoke/{provider}")
async def revoke_provider(provider: str):
    info = integration_manager.get(provider)
    if not info:
        raise HTTPException(status_code=404, detail="Provider not registered")
    await credential_store.revoke(provider)
    integration_manager.set_state(provider, IntegrationState.REVOKED)
    return {"status": "revoked"}


@router.get("/health/{provider}")
async def health_provider(provider: str):
    info = integration_manager.get(provider)
    if not info:
        raise HTTPException(status_code=404, detail="Provider not registered")
    state = integration_manager.get_state(provider)
    # simple health check: must be CONNECTED and not revoked
    healthy = state == IntegrationState.CONNECTED and not info.revoked
    if healthy:
        integration_manager.set_state(provider, IntegrationState.HEALTHY)
    return {"healthy": healthy, "state": integration_manager.get_state(provider).value if integration_manager.get_state(provider) else None}

@router.get("/validate/{provider}")
async def validate_provider(provider: str):
    info = integration_manager.get(provider)
    if not info:
        raise HTTPException(status_code=404, detail="Provider not registered")
    # validation placeholder: ensure required fields present
    required = ["oauth_token_url", "oauth_authorize_url"]
    missing = [f for f in required if not getattr(info, f)]
    valid = len(missing) == 0
    return {"valid": valid, "missing": missing}


@router.post("/activate/{provider}")
async def activate_provider(provider: str):
    info = integration_manager.get(provider)
    if not info:
        raise HTTPException(status_code=404, detail="Provider not registered")
    # can activate only from HEALTHY state
    if integration_manager.get_state(provider) != IntegrationState.HEALTHY:
        raise HTTPException(status_code=400, detail="Provider not healthy")
    integration_manager.set_state(provider, IntegrationState.ACTIVE)
    return {"status": "active"}

"""Central registry for all external integrations.

Each provider registers once with metadata, OAuth URLs, scopes, and capabilities.
The manager exposes status information used by health monitoring and the /integrations/status endpoint.
"""

from __future__ import annotations

import datetime
from typing import Dict, Any, List, Optional

from app.integrations.credential_store import credential_store
from app.integrations.lifecycle import IntegrationState
from app.config import settings


class ProviderInfo:
    def __init__(
        self,
        name: str,
        oauth_token_url: str,
        oauth_authorize_url: str,
        scopes: List[str],
        capabilities: List[str],
    ) -> None:
        self.name = name
        self.oauth_token_url = oauth_token_url
        self.oauth_authorize_url = oauth_authorize_url
        self.scopes = scopes
        self.capabilities = capabilities
        # runtime state placeholders
        self.last_refresh: Optional[datetime.datetime] = None
        self.last_error: Optional[str] = None
        self.revoked: bool = False
        self.quota_exhausted: bool = False
        self.rate_limited: bool = False
        self.latency_ms: Optional[float] = None

    def to_status(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "authenticated": not self.revoked,
            "last_refresh": self.last_refresh,
            "last_error": self.last_error,
            "scopes": self.scopes,
            "capabilities": self.capabilities,
            "quota_exhausted": self.quota_exhausted,
            "rate_limited": self.rate_limited,
            "latency_ms": self.latency_ms,
        }


class IntegrationManager:
    def __init__(self) -> None:
        self._providers: Dict[str, ProviderInfo] = {}
        # runtime lifecycle per provider
        from app.integrations.lifecycle import IntegrationState
        self._states: Dict[str, IntegrationState] = {}

    def register(
        self,
        name: str,
        oauth_token_url: str,
        oauth_authorize_url: str,
        scopes: List[str],
        capabilities: List[str],
    ) -> None:
        from app.integrations.lifecycle import IntegrationState
        if name in self._providers:
            # overwrite – deterministic last write wins (pony tail)
            pass
        self._providers[name] = ProviderInfo(name, oauth_token_url, oauth_authorize_url, scopes, capabilities)
        # initialise lifecycle state to UNCONFIGURED
        self._states[name] = IntegrationState.UNCONFIGURED

    def get(self, name: str) -> Optional[ProviderInfo]:
        return self._providers.get(name)

    def get_state(self, name: str) -> Optional[IntegrationState]:
        return self._states.get(name)

    def set_state(self, name: str, target: IntegrationState) -> bool:
        """Attempt to move *name* to *target* state.
        Returns True on success, False otherwise.
        """
        from app.integrations.lifecycle import validate_transition
        current = self._states.get(name)
        if not current:
            return False
        if validate_transition(current, target):
            self._states[name] = target
            return True
        return False

    def all_status(self) -> List[Dict[str, Any]]:
        result = []
        for name, p in self._providers.items():
            status = p.to_status()
            state_obj = self._states.get(name)
            authenticated = False
            if state_obj in (IntegrationState.CONNECTED, IntegrationState.ACTIVE):
                authenticated = not p.revoked
            status.update({
                "state": state_obj.value if state_obj else None,
                "authenticated": authenticated,
                "token_expiry": None,
                "last_refresh": p.last_refresh,
                "quota": None,
                "rate_limit": None,
                "health": None,
                "last_error": p.last_error,
                "last_webhook": None,
                "enabled_capabilities": p.capabilities,
            })
            result.append(status)
        return result

    # -------------------------------------------------------------------
    # Helper to refresh tokens using stored credentials and provider config
    # -------------------------------------------------------------------
    async def refresh_token(self, name: str) -> bool:
        provider = self.get(name)
        if not provider:
            return False
        cred = await credential_store.get(name)
        if not cred or not cred.get("refresh_token"):
            provider.last_error = "No refresh token"
            return False
        # Simple token refresh via HTTP POST – use httpx (already a dep)
        import httpx
        async with httpx.AsyncClient(timeout=10) as client:
            data = {
                "grant_type": "refresh_token",
                "refresh_token": cred["refresh_token"],
                "client_id": getattr(settings, f"{name.upper()}_CLIENT_ID"),
                "client_secret": getattr(settings, f"{name.upper()}_CLIENT_SECRET"),
                "scope": " ".join(provider.scopes),
            }
            try:
                resp = await client.post(provider.oauth_token_url, data=data)
                resp.raise_for_status()
                payload = resp.json()
                await credential_store.set(
                    provider=name,
                    access_token=payload["access_token"],
                    refresh_token=payload.get("refresh_token"),
                    expires_at=datetime.datetime.utcnow() + datetime.timedelta(seconds=int(payload.get("expires_in", 3600))),
                    scopes=provider.scopes,
                )
                provider.last_refresh = datetime.datetime.utcnow()
                provider.last_error = None
                provider.revoked = False
                return True
            except Exception as e:
                provider.last_error = str(e)
                return False

# Global singleton used throughout the app
integration_manager = IntegrationManager()

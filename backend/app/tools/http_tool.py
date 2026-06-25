from __future__ import annotations

import httpx

from app.runtime.tool_registry import registry

# ponytail: module-level client, reused across calls
_client = httpx.AsyncClient(timeout=10.0, follow_redirects=True)


async def http_get(url: str) -> str:
    """Perform a GET request and return the response body."""
    try:
        resp = await _client.get(url)
        resp.raise_for_status()
        return resp.text[:50000]  # ponytail: cap response size
    except httpx.HTTPError as e:
        return f"Error: {e}"


def register() -> None:
    registry.register(
        "http",
        "Perform an HTTP GET request to a URL",
        http_get,
        {"url": "URL to fetch"},
    )

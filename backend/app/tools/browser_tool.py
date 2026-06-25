from __future__ import annotations

import time

from app.intelligence.metrics import metrics
from app.runtime.browser_client import browser_client
from app.runtime.tool_registry import registry


async def open_url(url: str) -> str:
    """Open a URL in the browser."""
    start = time.perf_counter()
    result = await browser_client.execute("open_url", {"url": url})
    latency_ms = round((time.perf_counter() - start) * 1000, 2)
    metrics.record_browser(latency_ms, result.get("success", False))
    if result.get("success"):
        return result.get("message", f"Opened {url}")
    return f"Error: {result.get('error', 'Unknown error')}"


async def open_tab(url: str) -> str:
    """Open a new tab in the browser."""
    start = time.perf_counter()
    result = await browser_client.execute("open_tab", {"url": url})
    latency_ms = round((time.perf_counter() - start) * 1000, 2)
    metrics.record_browser(latency_ms, result.get("success", False))
    if result.get("success"):
        return result.get("message", f"Opened tab {url}")
    return f"Error: {result.get('error', 'Unknown error')}"


async def close_tab(tab_id: str = "") -> str:
    """Close a browser tab. Empty tab_id closes current tab."""
    start = time.perf_counter()
    payload = {"tab_id": tab_id} if tab_id else {}
    result = await browser_client.execute("close_tab", payload)
    latency_ms = round((time.perf_counter() - start) * 1000, 2)
    metrics.record_browser(latency_ms, result.get("success", False))
    if result.get("success"):
        return result.get("message", "Tab closed")
    return f"Error: {result.get('error', 'Unknown error')}"


async def activate_tab(tab_id: str = "") -> str:
    """Activate a browser tab. Empty tab_id activates current tab."""
    start = time.perf_counter()
    payload = {"tab_id": tab_id} if tab_id else {}
    result = await browser_client.execute("activate_tab", payload)
    latency_ms = round((time.perf_counter() - start) * 1000, 2)
    metrics.record_browser(latency_ms, result.get("success", False))
    if result.get("success"):
        return result.get("message", "Tab activated")
    return f"Error: {result.get('error', 'Unknown error')}"


async def search_google(query: str) -> str:
    """Search Google with the given query."""
    start = time.perf_counter()
    result = await browser_client.execute("search_google", {"query": query})
    latency_ms = round((time.perf_counter() - start) * 1000, 2)
    metrics.record_browser(latency_ms, result.get("success", False))
    if result.get("success"):
        return result.get("message", f"Searched for: {query}")
    return f"Error: {result.get('error', 'Unknown error')}"


def register() -> None:
    registry.register("browser_open_url", "Open a URL in the browser", open_url, {"url": "URL to open"})
    registry.register("browser_open_tab", "Open a new browser tab", open_tab, {"url": "URL to open"})
    registry.register("browser_close_tab", "Close a browser tab", close_tab, {"tab_id": "Tab ID (empty = current)"})
    registry.register("browser_activate_tab", "Activate a browser tab", activate_tab, {"tab_id": "Tab ID (empty = current)"})
    registry.register("browser_search_google", "Search Google", search_google, {"query": "Search query"})

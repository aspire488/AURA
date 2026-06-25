from __future__ import annotations

from datetime import datetime, timezone

from app.runtime.tool_registry import registry


async def current_time() -> str:
    """Return current UTC time as ISO string."""
    return datetime.now(timezone.utc).isoformat()


async def current_date() -> str:
    """Return current UTC date as ISO string."""
    return datetime.now(timezone.utc).date().isoformat()


def register() -> None:
    registry.register("time", "Get current time or date", current_time)
    registry.register("date", "Get current date", current_date)

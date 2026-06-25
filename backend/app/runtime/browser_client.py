from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class BrowserClient:
    """Singleton WebSocket transport to the browser extension.

    ponytail: one connection, one pending map, no queues.
    """

    _ws: object | None = None
    _pending: dict[str, asyncio.Future] = field(default_factory=dict)
    _connected_at: float = 0.0
    _last_health_ms: float = 0.0

    async def connect(self, ws: object) -> None:
        """Register a new browser extension connection."""
        import time

        self._ws = ws
        self._connected_at = time.monotonic()
        logger.info("Browser extension connected")

    async def disconnect(self) -> None:
        """Clean up on browser disconnect."""
        self._ws = None
        # Fail all pending requests
        for future in self._pending.values():
            if not future.done():
                future.set_exception(ConnectionError("Browser disconnected"))
        self._pending.clear()
        logger.info("Browser extension disconnected")

    def is_connected(self) -> bool:
        return self._ws is not None

    async def execute(self, action: str, payload: dict | None = None, timeout: float = 10.0) -> dict:
        """Send a command to the browser extension and wait for response.

        ponytail: send JSON, wait for matching id, timeout.
        """
        if not self._ws:
            return {"success": False, "error": "Browser extension not connected"}

        msg_id = uuid.uuid4().hex[:12]
        loop = asyncio.get_running_loop()
        future: asyncio.Future = loop.create_future()
        self._pending[msg_id] = future

        message = {"id": msg_id, "action": action}
        if payload:
            message.update(payload)

        try:
            await self._ws.send_json(message)
        except Exception as e:
            self._pending.pop(msg_id, None)
            return {"success": False, "error": f"Send failed: {e}"}

        try:
            result = await asyncio.wait_for(future, timeout=timeout)
            return result
        except asyncio.TimeoutError:
            self._pending.pop(msg_id, None)
            return {"success": False, "error": f"Timeout after {timeout}s waiting for browser response"}
        except ConnectionError:
            self._pending.pop(msg_id, None)
            return {"success": False, "error": "Browser disconnected while waiting for response"}

    async def handle_response(self, data: dict) -> None:
        """Forward a response from the extension to the waiting future."""
        msg_id = data.get("id")
        if not msg_id:
            return
        future = self._pending.pop(msg_id, None)
        if future and not future.done():
            future.set_result(data)

    def health(self) -> dict:
        """Return connection status."""
        import time

        return {
            "connected": self.is_connected(),
            "uptime_seconds": round(time.monotonic() - self._connected_at, 1) if self._connected_at else 0,
            "pending_requests": len(self._pending),
        }


# ponytail: module-level singleton
browser_client = BrowserClient()

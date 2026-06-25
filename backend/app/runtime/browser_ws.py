from __future__ import annotations

import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.runtime.browser_client import browser_client

logger = logging.getLogger(__name__)

router = APIRouter()


@router.websocket("/ws/browser")
async def browser_ws(ws: WebSocket):
    """Accept browser extension connection and forward messages.

    ponytail: accept, loop, forward responses, disconnect.
    """
    await ws.accept()
    await browser_client.connect(ws)
    try:
        while True:
            data = await ws.receive_json()
            await browser_client.handle_response(data)
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.warning("Browser WebSocket error: %s", e)
    finally:
        await browser_client.disconnect()

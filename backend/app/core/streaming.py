"""SSE streaming helper for /reason. ponytail: stdlib asyncio, no extra deps."""
from __future__ import annotations

import json
import asyncio
from typing import AsyncGenerator

from starlette.responses import StreamingResponse


async def stream_reason_response(
    query: str,
    session_id: str,
) -> StreamingResponse:
    """Stream reason response as SSE. ponytail: wraps existing kio pipeline.

    Sends events: thinking, step_update, result, done.
    """
    async def event_gen() -> AsyncGenerator[str, None]:
        from app.runtime.kio_adapter import kio, KIORequest
        from app.intelligence.metrics import metrics

        metrics.record_stream_request()
        yield f"data: {json.dumps({'type': 'thinking', 'message': 'Processing...'})}\n\n"

        request = KIORequest(query=query, session_id=session_id)
        try:
            result = await kio.process_request(request)
            yield f"data: {json.dumps({'type': 'result', 'answer': result.answer, 'intent': result.intent, 'citations': result.citations})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

        yield f"data: {json.dumps({'type': 'done'})}\n\n"

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )

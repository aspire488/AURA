import logging
import time
import traceback
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

logger = logging.getLogger("aura.request")


class RequestMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id

        start = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            elapsed_ms = round((time.perf_counter() - start) * 1000, 1)
            logger.error(
                "uncaught_exception",
                extra={"request_id": request_id, "path": request.url.path},
                exc_info=True,
            )
            return JSONResponse(
                status_code=500,
                content={"error": "internal_server_error", "message": "Unexpected server error."},
                headers={"X-Request-ID": request_id},
            )

        elapsed_ms = round((time.perf_counter() - start) * 1000, 1)
        logger.info(
            "%s %s -> %s (%sms) [%s]",
            request.method,
            request.url.path,
            response.status_code,
            elapsed_ms,
            request_id,
        )
        response.headers["X-Request-ID"] = request_id
        return response

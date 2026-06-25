import logging
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.core.logging import request_id_var, session_id_var
from app.intelligence.metrics import metrics
from app.runtime.rate_limiter import get_rate_limiter

logger = logging.getLogger("aura.request")

# ponytail: endpoints protected by rate limiter.
_RATE_LIMITED = {"/reason", "/browser/execute", "/code/execute"}


class RequestMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id
        request_id_var.set(request_id)

        # Rate limiting
        if request.url.path in _RATE_LIMITED and request.method == "POST":
            client_ip = request.client.host if request.client else "unknown"
            limiter = get_rate_limiter()
            if not limiter.allow(client_ip):
                metrics.record_rate_limit_hit()
                return JSONResponse(
                    status_code=429,
                    content={"error": "rate_limited", "message": "Too many requests"},
                    headers={"X-Request-ID": request_id, "Retry-After": "1"},
                )

        metrics.record_request_start()
        start = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            elapsed_ms = round((time.perf_counter() - start) * 1000, 1)
            logger.error(
                "uncaught_exception path=%s latency_ms=%s",
                request.url.path, elapsed_ms,
                exc_info=True,
            )
            return JSONResponse(
                status_code=500,
                content={"error": "internal_server_error", "message": "Unexpected server error."},
                headers={"X-Request-ID": request_id},
            )
        finally:
            metrics.record_request_end()

        elapsed_ms = round((time.perf_counter() - start) * 1000, 1)
        logger.info(
            "%s %s -> %s latency_ms=%s request_id=%s",
            request.method,
            request.url.path,
            response.status_code,
            elapsed_ms,
            request_id,
        )
        response.headers["X-Request-ID"] = request_id
        return response

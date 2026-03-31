"""
Structured JSON logging middleware.

Logs method, path, status, and duration for every request.
Binds ``request_id`` and ``user_id`` into the structlog context.

NOTE: In the middleware stack (request_id → logging → cors → rate_limit → auth),
auth runs *after* logging on the inbound path. Therefore ``user_id`` is bound
after ``call_next`` returns — it will appear in this middleware's own log line
but **not** in log lines emitted by inner middleware.  ``request_id`` is always
available because request_id middleware is outermost.
"""

import time

import structlog
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

logger = structlog.get_logger("forge.http")


class LoggingMiddleware(BaseHTTPMiddleware):
    """Emit a structured JSON log line per request."""

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        request_id = getattr(request.state, "request_id", "unknown")

        # Bind request_id immediately (available from outer middleware)
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=request_id)

        start = time.perf_counter()
        response = await call_next(request)
        duration_ms = round((time.perf_counter() - start) * 1000, 2)

        # Auth middleware has now run — user_id is available on request.state
        user = getattr(request.state, "user", None)
        user_id = user.get("sub", "anonymous") if isinstance(user, dict) else "anonymous"
        structlog.contextvars.bind_contextvars(user_id=user_id)

        logger.info(
            "http_request",
            method=request.method,
            path=str(request.url.path),
            status=response.status_code,
            duration_ms=duration_ms,
            user_id=user_id,
        )

        return response

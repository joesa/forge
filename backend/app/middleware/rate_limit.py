"""
Sliding-window rate limiter middleware.

Limits:
  • Standard routes: 100 req / min per user
  • AI-heavy routes (/api/v1/ai/*): 10 req / min per user

Returns ``429 Too Many Requests`` with a ``Retry-After`` header when
the limit is exceeded.
"""

import time
import uuid

import structlog
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.core.redis import get_redis

logger = structlog.get_logger(__name__)

# Paths that are AI-heavy and get a lower limit
_AI_PREFIX = "/api/v1/ai/"

_STANDARD_LIMIT = 100
_AI_LIMIT = 10
_WINDOW_SECONDS = 60


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Per-user sliding-window rate limiter backed by Redis sorted sets."""

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        # Identify the caller — use JWT sub or fall back to IP
        user = getattr(request.state, "user", None)
        if user and isinstance(user, dict):
            identity = user.get("sub", request.client.host if request.client else "unknown")
        else:
            identity = request.client.host if request.client else "unknown"

        is_ai = request.url.path.startswith(_AI_PREFIX)
        limit = _AI_LIMIT if is_ai else _STANDARD_LIMIT
        bucket = f"forge:rl:{'ai' if is_ai else 'std'}:{identity}"

        now = time.time()
        window_start = now - _WINDOW_SECONDS

        try:
            redis = await get_redis()
            pipe = redis.pipeline()
            # Remove entries outside the window
            pipe.zremrangebyscore(bucket, 0, window_start)
            # Count remaining entries
            pipe.zcard(bucket)
            # Add the current request — use UUID to avoid key collisions
            # when multiple requests arrive at the exact same timestamp
            member = f"{now}:{uuid.uuid4().hex[:8]}"
            pipe.zadd(bucket, {member: now})
            # Expire the key after the window
            pipe.expire(bucket, _WINDOW_SECONDS + 1)
            results = await pipe.execute()

            current_count: int = results[1]

            if current_count >= limit:
                # Compute how long until the oldest entry in the window
                # expires. Fetch the oldest score to calculate accurately.
                oldest_entries = await redis.zrange(bucket, 0, 0, withscores=True)
                if oldest_entries:
                    oldest_ts = oldest_entries[0][1]
                    retry_after = int((oldest_ts + _WINDOW_SECONDS) - now)
                else:
                    retry_after = _WINDOW_SECONDS

                logger.warning(
                    "rate_limit_exceeded",
                    identity=identity,
                    limit=limit,
                    path=request.url.path,
                )
                return JSONResponse(
                    status_code=429,
                    content={"detail": "Rate limit exceeded"},
                    headers={"Retry-After": str(max(retry_after, 1))},
                )
        except Exception as exc:
            # If Redis is down, allow the request through (fail-open)
            logger.error("rate_limit_redis_error", error=str(exc))

        return await call_next(request)

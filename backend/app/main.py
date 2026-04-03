"""
FORGE — FastAPI application entry point.

Middleware registration order (outermost → innermost):
  request_id → logging → cors → rate_limit → auth
"""

import structlog
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.core.redis import close_redis
from app.api.v1.auth import router as auth_router
from app.api.v1.pipeline import router as pipeline_router, internal_router
from app.api.v1.projects import router as projects_router
from app.api.v1.sandbox import (
    sandbox_router,
    preview_projects_router,
)
from app.api.v1.ideation import router as ideation_router
from app.api.v1.editor import router as editor_router
from app.api.v1.settings_routes import router as settings_router
from app.api.v1.build import router as build_router
from app.api.v1.ai import router as ai_router
from app.api.v1.webhooks import router as webhooks_router
from app.middleware.auth import AuthMiddleware
from app.middleware.logging import LoggingMiddleware
from app.middleware.rate_limit import RateLimitMiddleware
from app.middleware.request_id import RequestIdMiddleware

# ── Structlog configuration ─────────────────────────────────────────
structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.make_filtering_bound_logger(0),
    context_class=dict,
    logger_factory=structlog.PrintLoggerFactory(),
    cache_logger_on_first_use=True,
)

# ── Sentry (only in production) ─────────────────────────────────────
if settings.SENTRY_DSN and settings.is_production:
    import sentry_sdk
    from sentry_sdk.integrations.fastapi import FastApiIntegration

    sentry_sdk.init(
        dsn=settings.SENTRY_DSN,
        integrations=[FastApiIntegration()],
        traces_sample_rate=0.1,
    )

# ── Lifespan ─────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Startup / shutdown lifecycle."""
    yield
    await close_redis()


# ── App ──────────────────────────────────────────────────────────────
app = FastAPI(
    title="FORGE API",
    version="0.1.0",
    docs_url="/docs" if not settings.is_production else None,
    redoc_url=None,
    lifespan=lifespan,
)

# ── Middleware (registered inside-out: last added = outermost) ───────
# 5. Auth (innermost — runs last, after logging has bound request_id)
app.add_middleware(AuthMiddleware)

# 4. Rate-limit
app.add_middleware(RateLimitMiddleware)

# 3. CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FORGE_FRONTEND_URL],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 2. Logging
app.add_middleware(LoggingMiddleware)

# 1. Request-ID (outermost — runs first)
app.add_middleware(RequestIdMiddleware)


# ── Health check ─────────────────────────────────────────────────────
@app.get("/health", tags=["system"])
async def health_check() -> JSONResponse:
    """Lightweight liveness probe."""
    return JSONResponse(content={"status": "ok"})


# ── API routers ──────────────────────────────────────────────────────
app.include_router(auth_router)
app.include_router(pipeline_router)
app.include_router(projects_router)
app.include_router(sandbox_router)
app.include_router(preview_projects_router)
app.include_router(internal_router)
app.include_router(ideation_router)
app.include_router(editor_router)
app.include_router(settings_router)
app.include_router(build_router)
app.include_router(ai_router)
app.include_router(webhooks_router)

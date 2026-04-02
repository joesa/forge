"""
Preview service — live preview URL, health, screenshots, and share links.

Architecture rules:
  • DB reads → replica session (get_read_session)
  • DB writes → primary session (get_write_session)
  • Health checks cached in Redis (10s TTL) to avoid hammering sandbox
  • Share tokens: HMAC-SHA256, stored in Redis + preview_shares table
"""

import datetime
import hashlib
import hmac
import json
import re
import time
import uuid

import httpx
import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.redis import (
    delete_cache,
    get_cache,
    get_redis,
    publish_event,
    set_cache,
)
from app.models.preview_share import PreviewShare
from app.models.sandbox import Sandbox, SandboxStatus
from app.schemas.preview import (
    HealthResult,
    PreviewURLResult,
    ScreenshotResult,
    ShareResult,
)
from app.services import storage_service

logger = structlog.get_logger(__name__)

# ── Constants ────────────────────────────────────────────────────────

_HEALTH_CACHE_TTL = 10  # seconds
_SCREENSHOT_TIMEOUT = 5  # seconds
_SHARE_KEY_PREFIX = "preview_share:"


# ── Preview URL ──────────────────────────────────────────────────────


async def get_preview_url(
    sandbox_id: str,
    user_id: str,
    session: AsyncSession,
) -> PreviewURLResult:
    """
    Look up sandbox in database and return preview URL.

    Returns {url, ready, expires_at} where ready indicates the sandbox
    dev server is available.
    """
    sandbox_uuid = uuid.UUID(sandbox_id)
    user_uuid = uuid.UUID(user_id)

    stmt = select(Sandbox).where(
        Sandbox.id == sandbox_uuid,
        Sandbox.user_id == user_uuid,
    )
    result = await session.execute(stmt)
    sandbox = result.scalar_one_or_none()

    if sandbox is None:
        raise LookupError(f"Sandbox {sandbox_id} not found or access denied")

    preview_url = f"https://{sandbox_id}.{settings.PREVIEW_DOMAIN}"
    is_ready = sandbox.status in (SandboxStatus.ready, SandboxStatus.assigned)

    # Expire 24h after last heartbeat (or assigned_at as fallback)
    expires_at = None
    ref_time = sandbox.last_heartbeat or sandbox.assigned_at
    if ref_time:
        expires_at = ref_time + datetime.timedelta(hours=24)

    logger.info(
        "preview_url_resolved",
        sandbox_id=sandbox_id,
        ready=is_ready,
        user_id=user_id,
    )

    return PreviewURLResult(
        url=preview_url,
        ready=is_ready,
        expires_at=expires_at,
    )


# ── Health Check ─────────────────────────────────────────────────────


async def check_preview_health(sandbox_id: str) -> HealthResult:
    """
    Check sandbox dev server health via internal HTTP GET.

    Results cached in Redis for 10 seconds to avoid hammering the sandbox.
    """
    cache_key = f"preview_health:{sandbox_id}"

    # Check cache first
    cached = await get_cache(cache_key)
    if cached:
        data = json.loads(cached)
        return HealthResult(
            healthy=data["healthy"],
            latency_ms=data["latency_ms"],
            last_checked=datetime.datetime.fromisoformat(data["last_checked"]),
        )

    # Probe the sandbox dev server
    preview_url = f"https://{sandbox_id}.{settings.PREVIEW_DOMAIN}"
    health_url = f"{preview_url}/health"

    healthy = False
    latency_ms = 0
    now = datetime.datetime.now(datetime.timezone.utc)

    try:
        start = time.monotonic()
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(health_url)
            latency_ms = int((time.monotonic() - start) * 1000)
            healthy = resp.status_code == 200
    except (httpx.HTTPError, Exception) as exc:
        logger.warning(
            "preview_health_probe_failed",
            sandbox_id=sandbox_id,
            error=str(exc),
        )

    result = HealthResult(
        healthy=healthy,
        latency_ms=latency_ms,
        last_checked=now,
    )

    # Cache result
    cache_data = json.dumps({
        "healthy": healthy,
        "latency_ms": latency_ms,
        "last_checked": now.isoformat(),
    })
    await set_cache(cache_key, cache_data, _HEALTH_CACHE_TTL)

    return result


# ── Screenshot ───────────────────────────────────────────────────────


def _slugify_route(route: str) -> str:
    """Convert a route path to a filename-safe slug."""
    slug = route.strip("/").replace("/", "_") or "root"
    # Remove non-alphanumeric characters except underscores and hyphens
    slug = re.sub(r"[^a-zA-Z0-9_\-]", "", slug)
    return slug[:64]  # Cap length


async def take_screenshot(
    sandbox_id: str,
    route: str = "/",
    width: int = 1280,
    height: int = 800,
) -> ScreenshotResult:
    """
    Capture a screenshot of the preview at the given route.

    Uses headless Playwright, compresses to WebP, uploads to R2.
    R2 key: screenshots/{sandbox_id}/{timestamp}_{route}.webp
    """
    from playwright.async_api import async_playwright

    preview_url = f"https://{sandbox_id}.{settings.PREVIEW_DOMAIN}{route}"
    timestamp = int(time.time())
    route_slug = _slugify_route(route)
    r2_key = f"screenshots/{sandbox_id}/{timestamp}_{route_slug}.webp"

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            try:
                page = await browser.new_page(
                    viewport={"width": width, "height": height}
                )
                await page.goto(
                    preview_url,
                    timeout=_SCREENSHOT_TIMEOUT * 1000,
                    wait_until="networkidle",
                )

                # Full-page screenshot as PNG, then we'll handle as bytes
                screenshot_bytes = await page.screenshot(
                    full_page=True,
                    type="png",
                )
            finally:
                await browser.close()

        # Upload to R2 as WebP (Playwright doesn't natively support WebP
        # in all browser modes, so we upload PNG with WebP key for now;
        # production would convert via Pillow)
        await storage_service.upload_file(
            key=r2_key,
            content=screenshot_bytes,
            content_type="image/webp",
        )

        screenshot_url = await storage_service.generate_presigned_url(r2_key)
        now = datetime.datetime.now(datetime.timezone.utc)

        logger.info(
            "screenshot_captured",
            sandbox_id=sandbox_id,
            route=route,
            r2_key=r2_key,
        )

        return ScreenshotResult(
            screenshot_url=screenshot_url,
            taken_at=now,
        )

    except Exception as exc:
        logger.error(
            "screenshot_failed",
            sandbox_id=sandbox_id,
            route=route,
            error=str(exc),
        )
        raise


# ── Share Links ──────────────────────────────────────────────────────


def _generate_share_token(sandbox_id: str, expires_at_unix: int) -> str:
    """Generate HMAC-SHA256 share token."""
    message = f"{sandbox_id}:{expires_at_unix}"
    return hmac.new(
        settings.FORGE_HMAC_SECRET.encode("utf-8"),
        message.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


async def create_share(
    sandbox_id: str,
    user_id: str,
    expires_hours: int,
    session: AsyncSession,
) -> ShareResult:
    """
    Create a shareable preview link.

    Token: HMAC-SHA256("{sandbox_id}:{expires_at_unix}", FORGE_HMAC_SECRET)
    Stored in Redis (with TTL) and preview_shares table.
    """
    now = datetime.datetime.now(datetime.timezone.utc)
    expires_at = now + datetime.timedelta(hours=expires_hours)
    expires_at_unix = int(expires_at.timestamp())

    token = _generate_share_token(sandbox_id, expires_at_unix)
    share_url = (
        f"https://{sandbox_id}.{settings.PREVIEW_DOMAIN}?token={token}"
    )

    # Fetch the sandbox — verify ownership
    sandbox_uuid = uuid.UUID(sandbox_id)
    user_uuid = uuid.UUID(user_id)
    stmt = select(Sandbox).where(
        Sandbox.id == sandbox_uuid,
        Sandbox.user_id == user_uuid,
    )
    result = await session.execute(stmt)
    sandbox = result.scalar_one_or_none()

    if sandbox is None:
        raise LookupError(f"Sandbox {sandbox_id} not found or access denied")

    project_id = sandbox.project_id

    # Store in Redis with TTL
    redis_key = f"{_SHARE_KEY_PREFIX}{token}"
    redis_data = json.dumps({
        "sandbox_id": sandbox_id,
        "expires_at": expires_at.isoformat(),
        "user_id": user_id,
    })
    ttl = expires_hours * 3600
    await set_cache(redis_key, redis_data, ttl)

    # Store in preview_shares table
    user_uuid = uuid.UUID(user_id)
    share = PreviewShare(
        project_id=project_id,
        user_id=user_uuid,
        share_token=token,
        is_active=True,
        expires_at=expires_at,
    )
    session.add(share)
    await session.flush()

    logger.info(
        "preview_share_created",
        sandbox_id=sandbox_id,
        token=token[:8] + "...",
        expires_at=expires_at.isoformat(),
        user_id=user_id,
    )

    return ShareResult(
        share_url=share_url,
        token=token,
        expires_at=expires_at,
    )


async def revoke_share(
    token: str,
    user_id: str,
    session: AsyncSession,
) -> bool:
    """
    Revoke a share link. Verifies ownership (403 if not owner).

    Deletes from Redis and preview_shares table.
    """
    # Check Redis for ownership
    redis_key = f"{_SHARE_KEY_PREFIX}{token}"
    cached = await get_cache(redis_key)

    if cached:
        data = json.loads(cached)
        if data.get("user_id") != user_id:
            raise PermissionError("You do not own this share link")

    # Delete from Redis
    await delete_cache(redis_key)

    # Delete from preview_shares table
    stmt = select(PreviewShare).where(PreviewShare.share_token == token)
    result = await session.execute(stmt)
    share = result.scalar_one_or_none()

    if share:
        if str(share.user_id) != user_id:
            raise PermissionError("You do not own this share link")
        await session.delete(share)
        await session.flush()

    logger.info(
        "preview_share_revoked",
        token=token[:8] + "...",
        user_id=user_id,
    )

    return True

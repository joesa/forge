"""
Webhook API routes (3 endpoints).

Receives callbacks from external services:
  - Trigger.dev (job status updates)
  - Northflank (container events)
  - GitHub (push, PR events)

All webhook endpoints validate signatures to prevent spoofing.
"""

from __future__ import annotations

import hashlib
import hmac

import structlog
from fastapi import APIRouter, Header, Request
from fastapi.responses import JSONResponse

from app.config import settings

logger = structlog.get_logger()

router = APIRouter(prefix="/api/v1/webhooks", tags=["webhooks"])


def _verify_signature(
    payload: bytes,
    signature: str,
    secret: str,
    algorithm: str = "sha256",
) -> bool:
    """Verify HMAC webhook signature."""
    expected = hmac.new(
        secret.encode(),
        payload,
        hashlib.sha256 if algorithm == "sha256" else hashlib.sha1,
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


@router.post("/trigger-dev")
async def trigger_dev_webhook(
    request: Request,
    x_trigger_signature: str = Header(default=""),
) -> JSONResponse:
    """Receive Trigger.dev job status webhooks."""
    body = await request.body()

    if not _verify_signature(body, x_trigger_signature, settings.FORGE_INTERNAL_SECRET):
        logger.warning("trigger_dev_webhook_invalid_signature")
        return JSONResponse(status_code=403, content={"detail": "Invalid signature"})

    payload = await request.json()
    event_type = payload.get("type", "unknown")

    logger.info(
        "trigger_dev_webhook_received",
        event_type=event_type,
        job_id=payload.get("jobId"),
    )

    return JSONResponse(content={"received": True})


@router.post("/northflank")
async def northflank_webhook(
    request: Request,
    x_northflank_signature: str = Header(default=""),
) -> JSONResponse:
    """Receive Northflank container event webhooks."""
    body = await request.body()

    if not _verify_signature(body, x_northflank_signature, settings.FORGE_INTERNAL_SECRET):
        logger.warning("northflank_webhook_invalid_signature")
        return JSONResponse(status_code=403, content={"detail": "Invalid signature"})

    payload = await request.json()
    event_type = payload.get("event", "unknown")

    logger.info(
        "northflank_webhook_received",
        event_type=event_type,
        resource_id=payload.get("resourceId"),
    )

    return JSONResponse(content={"received": True})


@router.post("/github")
async def github_webhook(
    request: Request,
    x_hub_signature_256: str = Header(default=""),
) -> JSONResponse:
    """Receive GitHub push/PR webhooks."""
    body = await request.body()

    signature = x_hub_signature_256.replace("sha256=", "")
    if not _verify_signature(body, signature, settings.FORGE_INTERNAL_SECRET):
        logger.warning("github_webhook_invalid_signature")
        return JSONResponse(status_code=403, content={"detail": "Invalid signature"})

    payload = await request.json()
    event_type = request.headers.get("X-GitHub-Event", "unknown")

    logger.info(
        "github_webhook_received",
        event_type=event_type,
        repo=payload.get("repository", {}).get("full_name"),
    )

    return JSONResponse(content={"received": True})

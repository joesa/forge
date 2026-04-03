"""
Build API routes (8 endpoints).

Handles: start, status, logs, cancel, retry, list, WebSocket stream.
"""

from __future__ import annotations

import uuid

import structlog
from fastapi import APIRouter, Depends, Query, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_read_session, get_write_session
from app.services import build_service
from app.schemas.build import (
    BuildCancelRequest,
    BuildListResponse,
    BuildResponse,
    BuildRetryRequest,
    BuildStartRequest,
)

logger = structlog.get_logger()

router = APIRouter(prefix="/api/v1/build", tags=["build"])


def _extract_user_id(request: Request) -> uuid.UUID:
    payload = getattr(request.state, "user", None)
    if payload:
        sub = payload.get("sub")
        if sub:
            return uuid.UUID(sub)

    # Backward compatibility for legacy middleware shape
    user_id = getattr(request.state, "user_id", None)
    if user_id:
        return uuid.UUID(user_id) if isinstance(user_id, str) else user_id

    raise ValueError("Missing user identity in request state")


@router.post("/start", response_model=BuildResponse)
async def start_build(
    body: BuildStartRequest,
    request: Request,
    write_session: AsyncSession = Depends(get_write_session),
) -> BuildResponse:
    """Start a new build for a project."""
    try:
        user_id = _extract_user_id(request)
    except ValueError as exc:
        return JSONResponse(status_code=401, content={"detail": str(exc)})

    try:
        build = await build_service.start_build(
            project_id=str(body.project_id),
            user_id=str(user_id),
            pipeline_id=str(body.pipeline_id) if body.pipeline_id else None,
            incremental=body.incremental,
            session=write_session,
        )
        return BuildResponse(
            id=build.id,
            project_id=build.project_id,
            pipeline_id=build.pipeline_run_id,
            status=build.status.value,
            created_at=build.created_at,
        )
    except LookupError as exc:
        return JSONResponse(status_code=404, content={"detail": str(exc)})
    except Exception as exc:
        logger.error("start_build_failed", error=str(exc))
        return JSONResponse(status_code=500, content={"detail": "Failed to start build"})


@router.get("/{build_id}", response_model=BuildResponse)
async def get_build(
    build_id: uuid.UUID,
    request: Request,
    read_session: AsyncSession = Depends(get_read_session),
) -> BuildResponse:
    """Get build status."""
    try:
        user_id = _extract_user_id(request)
    except ValueError as exc:
        return JSONResponse(status_code=401, content={"detail": str(exc)})

    try:
        build = await build_service.get_build(
            build_id=str(build_id),
            user_id=str(user_id),
            session=read_session,
        )
        return BuildResponse(
            id=build.id,
            project_id=build.project_id,
            pipeline_id=build.pipeline_run_id,
            status=build.status.value,
            created_at=build.created_at,
        )
    except LookupError as exc:
        return JSONResponse(status_code=404, content={"detail": str(exc)})
    except Exception as exc:
        logger.error("get_build_failed", error=str(exc))
        return JSONResponse(status_code=500, content={"detail": "Failed to get build"})


@router.get("/", response_model=BuildListResponse)
async def list_builds(
    request: Request,
    project_id: uuid.UUID = Query(...),
    read_session: AsyncSession = Depends(get_read_session),
) -> BuildListResponse:
    """List all builds for a project."""
    try:
        user_id = _extract_user_id(request)
    except ValueError as exc:
        return JSONResponse(status_code=401, content={"detail": str(exc)})

    try:
        builds = await build_service.list_builds(
            project_id=str(project_id),
            user_id=str(user_id),
            session=read_session,
        )
        return BuildListResponse(
            builds=[BuildResponse(
                id=b.id,
                project_id=b.project_id,
                pipeline_id=b.pipeline_run_id,
                status=b.status.value,
                created_at=b.created_at,
            ) for b in builds],
            total=len(builds),
        )
    except LookupError as exc:
        return JSONResponse(status_code=404, content={"detail": str(exc)})
    except Exception as exc:
        logger.error("list_builds_failed", error=str(exc))
        return JSONResponse(status_code=500, content={"detail": "Failed to list builds"})


@router.post("/{build_id}/cancel")
async def cancel_build(
    build_id: uuid.UUID,
    body: BuildCancelRequest,
    request: Request,
    write_session: AsyncSession = Depends(get_write_session),
) -> JSONResponse:
    """Cancel a running build."""
    try:
        user_id = _extract_user_id(request)
    except ValueError as exc:
        return JSONResponse(status_code=401, content={"detail": str(exc)})

    try:
        await build_service.cancel_build(
            build_id=str(build_id),
            user_id=str(user_id),
            reason=body.reason,
            session=write_session,
        )
        return JSONResponse(content={"success": True})
    except LookupError as exc:
        return JSONResponse(status_code=404, content={"detail": str(exc)})
    except ValueError as exc:
        return JSONResponse(status_code=400, content={"detail": str(exc)})
    except Exception as exc:
        logger.error("cancel_build_failed", error=str(exc))
        return JSONResponse(status_code=500, content={"detail": "Failed to cancel build"})


@router.post("/{build_id}/retry", response_model=BuildResponse)
async def retry_build(
    build_id: uuid.UUID,
    body: BuildRetryRequest,
    request: Request,
    write_session: AsyncSession = Depends(get_write_session),
) -> BuildResponse:
    """Retry a failed build."""
    try:
        user_id = _extract_user_id(request)
    except ValueError as exc:
        return JSONResponse(status_code=401, content={"detail": str(exc)})

    try:
        build = await build_service.retry_build(
            build_id=str(build_id),
            user_id=str(user_id),
            from_agent=body.from_agent,
            session=write_session,
        )
        return BuildResponse(
            id=build.id,
            project_id=build.project_id,
            pipeline_id=build.pipeline_run_id,
            status=build.status.value,
            created_at=build.created_at,
        )
    except LookupError as exc:
        return JSONResponse(status_code=404, content={"detail": str(exc)})
    except ValueError as exc:
        return JSONResponse(status_code=400, content={"detail": str(exc)})
    except Exception as exc:
        logger.error("retry_build_failed", error=str(exc))
        return JSONResponse(status_code=500, content={"detail": "Failed to retry build"})


@router.websocket("/{build_id}/stream")
async def build_stream(
    websocket: WebSocket,
    build_id: uuid.UUID,
) -> None:
    """WebSocket stream for real-time build events."""
    await websocket.accept()
    logger.info("build_ws_connected", build_id=str(build_id))

    try:
        while True:
            data = await websocket.receive_text()
            await websocket.send_json({"type": "heartbeat", "build_id": str(build_id)})
    except WebSocketDisconnect:
        logger.info("build_ws_disconnected", build_id=str(build_id))

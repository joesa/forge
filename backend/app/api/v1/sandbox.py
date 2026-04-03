"""
Sandbox & Preview API — v1.

Sandbox-scoped routes (preview URL, health, screenshots, shares, console WS).
Project-scoped routes (snapshots, annotations).

All endpoints require authentication (enforced by AuthMiddleware).
Sandbox routes verify sandbox.user_id == current_user.id.
Project routes verify project.user_id == current_user.id.

Endpoints:
  GET    /api/v1/sandbox/{id}/preview-url
  GET    /api/v1/sandbox/{id}/preview/health
  POST   /api/v1/sandbox/{id}/preview/screenshot
  POST   /api/v1/sandbox/{id}/preview/share
  DELETE /api/v1/sandbox/{id}/preview/share/{token}
  WS     /api/v1/sandbox/{id}/console
  GET    /api/v1/projects/{id}/preview/snapshots
  GET    /api/v1/projects/{id}/annotations
  POST   /api/v1/projects/{id}/annotations
  DELETE /api/v1/projects/{id}/annotations/{annotation_id}
  DELETE /api/v1/projects/{id}/annotations
"""

import asyncio
import json
import uuid

import structlog
from fastapi import APIRouter, Depends, Query, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_read_session, get_write_session
from app.core.redis import get_redis
from app.schemas.preview import (
    AnnotationAIContextResponse,
    AnnotationCreateRequest,
    AnnotationListResponse,
    AnnotationResponse,
    HealthResult,
    MessageResponse,
    PreviewURLResult,
    ScreenshotRequest,
    ScreenshotResult,
    ShareRequest,
    ShareResult,
    SnapshotListResponse,
    SnapshotResponse,
)
from app.services import (
    annotation_service,
    file_sync_service,
    preview_service,
    snapshot_service,
)

logger = structlog.get_logger(__name__)

# ── Routers ──────────────────────────────────────────────────────────

sandbox_router = APIRouter(prefix="/api/v1/sandbox", tags=["sandbox"])
preview_projects_router = APIRouter(
    prefix="/api/v1/projects", tags=["preview"]
)


# ── Helpers ──────────────────────────────────────────────────────────


def _extract_user_id(request: Request) -> uuid.UUID:
    """Pull user ID from the JWT payload attached by AuthMiddleware."""
    payload = getattr(request.state, "user", None)
    if not payload:
        raise ValueError("No user payload in request state")
    sub = payload.get("sub")
    if not sub:
        raise ValueError("JWT missing 'sub' claim")
    return uuid.UUID(sub)


# ══════════════════════════════════════════════════════════════════════
# SANDBOX ROUTES
# ══════════════════════════════════════════════════════════════════════


@sandbox_router.post("", response_model=None)
async def create_sandbox(
    request: Request,
    write_session: AsyncSession = Depends(get_write_session),
) -> JSONResponse:
    """Claim a sandbox from the pre-warmed pool."""
    try:
        user_id = _extract_user_id(request)
    except ValueError as exc:
        return JSONResponse(status_code=401, content={"detail": str(exc)})

    try:
        body = await request.json()
        project_id = body.get("project_id")
        if not project_id:
            return JSONResponse(status_code=400, content={"detail": "project_id required"})
        sandbox = await sandbox_service.create_sandbox(
            project_id=project_id,
            user_id=str(user_id),
            session=write_session,
        )
        return JSONResponse(status_code=201, content={
            "id": str(sandbox.id),
            "status": sandbox.status.value if hasattr(sandbox.status, "value") else str(sandbox.status),
            "vm_url": sandbox.vm_url,
        })
    except Exception as exc:
        logger.error("create_sandbox_failed", error=str(exc))
        return JSONResponse(status_code=500, content={"detail": "Failed to create sandbox"})


@sandbox_router.post("/{sandbox_id}/start")
async def start_sandbox(
    sandbox_id: uuid.UUID,
    request: Request,
    write_session: AsyncSession = Depends(get_write_session),
) -> JSONResponse:
    """Start a sandbox."""
    try:
        user_id = _extract_user_id(request)
    except ValueError as exc:
        return JSONResponse(status_code=401, content={"detail": str(exc)})

    try:
        sandbox = await sandbox_service.get_sandbox(str(sandbox_id), str(user_id), write_session)
        return JSONResponse(content={"id": str(sandbox.id), "status": "assigned"})
    except LookupError as exc:
        return JSONResponse(status_code=404, content={"detail": str(exc)})
    except Exception as exc:
        logger.error("start_sandbox_failed", error=str(exc))
        return JSONResponse(status_code=500, content={"detail": "Failed to start sandbox"})


@sandbox_router.post("/{sandbox_id}/stop")
async def stop_sandbox(
    sandbox_id: uuid.UUID,
    request: Request,
    write_session: AsyncSession = Depends(get_write_session),
) -> JSONResponse:
    """Stop a running sandbox."""
    try:
        user_id = _extract_user_id(request)
    except ValueError as exc:
        return JSONResponse(status_code=401, content={"detail": str(exc)})

    try:
        await sandbox_service.stop_sandbox(str(sandbox_id), str(user_id), write_session)
        return JSONResponse(content={"success": True})
    except LookupError as exc:
        return JSONResponse(status_code=404, content={"detail": str(exc)})
    except Exception as exc:
        logger.error("stop_sandbox_failed", error=str(exc))
        return JSONResponse(status_code=500, content={"detail": "Failed to stop sandbox"})


@sandbox_router.delete("/{sandbox_id}")
async def destroy_sandbox(
    sandbox_id: uuid.UUID,
    request: Request,
    write_session: AsyncSession = Depends(get_write_session),
) -> JSONResponse:
    """Destroy a sandbox and release resources."""
    try:
        user_id = _extract_user_id(request)
    except ValueError as exc:
        return JSONResponse(status_code=401, content={"detail": str(exc)})

    try:
        await sandbox_service.destroy_sandbox(str(sandbox_id), str(user_id), write_session)
        return JSONResponse(content={"success": True})
    except LookupError as exc:
        return JSONResponse(status_code=404, content={"detail": str(exc)})
    except Exception as exc:
        logger.error("destroy_sandbox_failed", error=str(exc))
        return JSONResponse(status_code=500, content={"detail": "Failed to destroy sandbox"})


@sandbox_router.post("/{sandbox_id}/exec")
async def exec_command(
    sandbox_id: uuid.UUID,
    request: Request,
    write_session: AsyncSession = Depends(get_write_session),
) -> JSONResponse:
    """Execute a command in the sandbox."""
    try:
        user_id = _extract_user_id(request)
    except ValueError as exc:
        return JSONResponse(status_code=401, content={"detail": str(exc)})

    try:
        body = await request.json()
        command = body.get("command", "")
        output = await sandbox_service.execute_command(
            str(sandbox_id), str(user_id), command, write_session,
        )
        return JSONResponse(content={"output": output})
    except LookupError as exc:
        return JSONResponse(status_code=404, content={"detail": str(exc)})
    except Exception as exc:
        logger.error("exec_command_failed", error=str(exc))
        return JSONResponse(status_code=500, content={"detail": "Failed to execute command"})


@sandbox_router.websocket("/{sandbox_id}/terminal")
async def ws_terminal(
    websocket: WebSocket,
    sandbox_id: uuid.UUID,
) -> None:
    """WebSocket terminal for interactive sandbox shell."""
    await websocket.accept()
    logger.info("terminal_ws_connected", sandbox_id=str(sandbox_id))

    try:
        while True:
            data = await websocket.receive_text()
            # Echo for now — will be replaced with real sandbox terminal I/O
            await websocket.send_json({
                "type": "output",
                "data": f"$ {data}\n",
            })
    except WebSocketDisconnect:
        logger.info("terminal_ws_disconnected", sandbox_id=str(sandbox_id))


@sandbox_router.get(
    "/{sandbox_id}/preview-url", response_model=PreviewURLResult
)
async def get_preview_url(
    sandbox_id: uuid.UUID,
    request: Request,
    read_session: AsyncSession = Depends(get_read_session),
) -> PreviewURLResult | JSONResponse:
    """Get the preview URL for a sandbox."""
    try:
        user_id = _extract_user_id(request)
    except ValueError as exc:
        return JSONResponse(status_code=401, content={"detail": str(exc)})

    try:
        result = await preview_service.get_preview_url(
            sandbox_id=str(sandbox_id),
            user_id=str(user_id),
            session=read_session,
        )
        return result
    except LookupError as exc:
        return JSONResponse(status_code=404, content={"detail": str(exc)})
    except Exception as exc:
        logger.error("get_preview_url_failed", error=str(exc))
        return JSONResponse(
            status_code=500,
            content={"detail": "Failed to get preview URL"},
        )


@sandbox_router.get(
    "/{sandbox_id}/preview/health", response_model=HealthResult
)
async def check_preview_health(
    sandbox_id: uuid.UUID,
    request: Request,
    read_session: AsyncSession = Depends(get_read_session),
) -> HealthResult | JSONResponse:
    """Check the health of a sandbox preview server."""
    try:
        user_id = _extract_user_id(request)
    except ValueError as exc:
        return JSONResponse(status_code=401, content={"detail": str(exc)})

    try:
        result = await preview_service.check_preview_health(
            sandbox_id=str(sandbox_id),
            user_id=str(user_id),
            session=read_session,
        )
        return result
    except LookupError as exc:
        return JSONResponse(status_code=404, content={"detail": str(exc)})
    except Exception as exc:
        logger.error("check_preview_health_failed", error=str(exc))
        return JSONResponse(
            status_code=500,
            content={"detail": "Failed to check preview health"},
        )


@sandbox_router.post(
    "/{sandbox_id}/preview/screenshot", response_model=ScreenshotResult
)
async def take_screenshot(
    sandbox_id: uuid.UUID,
    body: ScreenshotRequest,
    request: Request,
    read_session: AsyncSession = Depends(get_read_session),
) -> ScreenshotResult | JSONResponse:
    """Capture a screenshot of the sandbox preview."""
    try:
        user_id = _extract_user_id(request)
    except ValueError as exc:
        return JSONResponse(status_code=401, content={"detail": str(exc)})

    try:
        # Verify ownership before allowing screenshot
        await preview_service.verify_sandbox_ownership(
            sandbox_id=str(sandbox_id),
            user_id=str(user_id),
            session=read_session,
        )
        result = await preview_service.take_screenshot(
            sandbox_id=str(sandbox_id),
            route=body.route,
            width=body.width,
            height=body.height,
        )
        return result
    except LookupError as exc:
        return JSONResponse(status_code=404, content={"detail": str(exc)})
    except Exception as exc:
        logger.error("take_screenshot_failed", error=str(exc))
        return JSONResponse(
            status_code=500,
            content={"detail": "Failed to capture screenshot"},
        )


@sandbox_router.post(
    "/{sandbox_id}/preview/share", response_model=ShareResult
)
async def create_share(
    sandbox_id: uuid.UUID,
    body: ShareRequest,
    request: Request,
    write_session: AsyncSession = Depends(get_write_session),
) -> ShareResult | JSONResponse:
    """Create a shareable preview link."""
    try:
        user_id = _extract_user_id(request)
    except ValueError as exc:
        return JSONResponse(status_code=401, content={"detail": str(exc)})

    try:
        result = await preview_service.create_share(
            sandbox_id=str(sandbox_id),
            user_id=str(user_id),
            expires_hours=body.expires_hours,
            session=write_session,
        )
        return result
    except LookupError as exc:
        return JSONResponse(status_code=404, content={"detail": str(exc)})
    except Exception as exc:
        logger.error("create_share_failed", error=str(exc))
        return JSONResponse(
            status_code=500,
            content={"detail": "Failed to create share link"},
        )


@sandbox_router.delete(
    "/{sandbox_id}/preview/share/{token}",
    response_model=MessageResponse,
)
async def revoke_share(
    sandbox_id: uuid.UUID,
    token: str,
    request: Request,
    write_session: AsyncSession = Depends(get_write_session),
) -> MessageResponse | JSONResponse:
    """Revoke a share link."""
    try:
        user_id = _extract_user_id(request)
    except ValueError as exc:
        return JSONResponse(status_code=401, content={"detail": str(exc)})

    try:
        await preview_service.revoke_share(
            token=token,
            user_id=str(user_id),
            session=write_session,
        )
        return MessageResponse(message="Share link revoked")
    except PermissionError as exc:
        return JSONResponse(status_code=403, content={"detail": str(exc)})
    except Exception as exc:
        logger.error("revoke_share_failed", error=str(exc))
        return JSONResponse(
            status_code=500,
            content={"detail": "Failed to revoke share link"},
        )


# ── WebSocket Console ────────────────────────────────────────────────


@sandbox_router.websocket("/{sandbox_id}/console")
async def ws_console(
    websocket: WebSocket,
    sandbox_id: uuid.UUID,
) -> None:
    """
    Stream dev console output in real-time.

    Subscribes to Redis channel "console:{sandbox_id}" and forwards
    messages to the WebSocket client.
    """
    await websocket.accept()

    redis = await get_redis()
    pubsub = redis.pubsub()
    channel = f"console:{sandbox_id}"

    try:
        await pubsub.subscribe(channel)

        while True:
            message = await pubsub.get_message(
                ignore_subscribe_messages=True,
                timeout=1.0,
            )
            if message and message["type"] == "message":
                data = message["data"]
                if isinstance(data, bytes):
                    data = data.decode("utf-8")
                await websocket.send_text(data)

            # Check for incoming messages from client (ping/pong, close)
            try:
                client_msg = await asyncio.wait_for(
                    websocket.receive_text(), timeout=0.01
                )
                # Client can send "ping" to keep alive
                if client_msg == "ping":
                    await websocket.send_text("pong")
            except asyncio.TimeoutError:
                pass
            except WebSocketDisconnect:
                break

    except WebSocketDisconnect:
        pass
    except Exception as exc:
        logger.error(
            "ws_console_error",
            sandbox_id=str(sandbox_id),
            error=str(exc),
        )
    finally:
        await pubsub.unsubscribe(channel)
        await pubsub.close()


# ══════════════════════════════════════════════════════════════════════
# PROJECT ROUTES — Snapshots & Annotations
# ══════════════════════════════════════════════════════════════════════


@preview_projects_router.get(
    "/{project_id}/preview/snapshots",
    response_model=SnapshotListResponse,
)
async def get_snapshots(
    project_id: uuid.UUID,
    request: Request,
    build_id: uuid.UUID | None = Query(default=None),
    read_session: AsyncSession = Depends(get_read_session),
) -> SnapshotListResponse | JSONResponse:
    """Get build snapshots for a project."""
    try:
        user_id = _extract_user_id(request)
    except ValueError as exc:
        return JSONResponse(status_code=401, content={"detail": str(exc)})

    try:
        snapshots = await snapshot_service.get_snapshots(
            project_id=str(project_id),
            user_id=str(user_id),
            build_id=str(build_id) if build_id else None,
            session=read_session,
        )
        return SnapshotListResponse(
            items=[
                SnapshotResponse.model_validate(s) for s in snapshots
            ],
            count=len(snapshots),
        )
    except LookupError as exc:
        return JSONResponse(status_code=404, content={"detail": str(exc)})
    except Exception as exc:
        logger.error("get_snapshots_failed", error=str(exc))
        return JSONResponse(
            status_code=500,
            content={"detail": "Failed to get snapshots"},
        )


@preview_projects_router.get(
    "/{project_id}/annotations",
    response_model=AnnotationListResponse,
)
async def get_annotations(
    project_id: uuid.UUID,
    request: Request,
    include_resolved: bool = Query(default=False),
    read_session: AsyncSession = Depends(get_read_session),
) -> AnnotationListResponse | JSONResponse:
    """Get annotations for a project."""
    try:
        user_id = _extract_user_id(request)
    except ValueError as exc:
        return JSONResponse(status_code=401, content={"detail": str(exc)})

    try:
        annotations = await annotation_service.get_annotations(
            project_id=str(project_id),
            user_id=str(user_id),
            include_resolved=include_resolved,
            session=read_session,
        )
        return AnnotationListResponse(
            items=[
                AnnotationResponse.model_validate(a) for a in annotations
            ],
            count=len(annotations),
        )
    except LookupError as exc:
        return JSONResponse(status_code=404, content={"detail": str(exc)})
    except Exception as exc:
        logger.error("get_annotations_failed", error=str(exc))
        return JSONResponse(
            status_code=500,
            content={"detail": "Failed to get annotations"},
        )


@preview_projects_router.post(
    "/{project_id}/annotations",
    response_model=AnnotationResponse,
    status_code=201,
)
async def create_annotation(
    project_id: uuid.UUID,
    body: AnnotationCreateRequest,
    request: Request,
    write_session: AsyncSession = Depends(get_write_session),
) -> AnnotationResponse | JSONResponse:
    """Create a new annotation."""
    try:
        user_id = _extract_user_id(request)
    except ValueError as exc:
        return JSONResponse(status_code=401, content={"detail": str(exc)})

    try:
        annotation = await annotation_service.create_annotation(
            project_id=str(project_id),
            user_id=str(user_id),
            session_id=body.session_id,
            css_selector=body.css_selector,
            route=body.route,
            comment=body.comment,
            x_pct=body.x_pct,
            y_pct=body.y_pct,
            session=write_session,
        )
        return AnnotationResponse.model_validate(annotation)
    except LookupError as exc:
        return JSONResponse(status_code=404, content={"detail": str(exc)})
    except ValueError as exc:
        return JSONResponse(status_code=422, content={"detail": str(exc)})
    except Exception as exc:
        logger.error("create_annotation_failed", error=str(exc))
        return JSONResponse(
            status_code=500,
            content={"detail": "Failed to create annotation"},
        )


@preview_projects_router.delete(
    "/{project_id}/annotations/{annotation_id}",
    response_model=MessageResponse,
)
async def delete_annotation(
    project_id: uuid.UUID,
    annotation_id: uuid.UUID,
    request: Request,
    write_session: AsyncSession = Depends(get_write_session),
) -> MessageResponse | JSONResponse:
    """Delete a single annotation."""
    try:
        user_id = _extract_user_id(request)
    except ValueError as exc:
        return JSONResponse(status_code=401, content={"detail": str(exc)})

    try:
        await annotation_service.delete_annotation(
            annotation_id=str(annotation_id),
            user_id=str(user_id),
            session=write_session,
        )
        return MessageResponse(message="Annotation deleted")
    except LookupError as exc:
        return JSONResponse(status_code=404, content={"detail": str(exc)})
    except Exception as exc:
        logger.error("delete_annotation_failed", error=str(exc))
        return JSONResponse(
            status_code=500,
            content={"detail": "Failed to delete annotation"},
        )


@preview_projects_router.delete(
    "/{project_id}/annotations",
    response_model=MessageResponse,
)
async def clear_annotations(
    project_id: uuid.UUID,
    request: Request,
    write_session: AsyncSession = Depends(get_write_session),
) -> MessageResponse | JSONResponse:
    """Delete all annotations for a project."""
    try:
        user_id = _extract_user_id(request)
    except ValueError as exc:
        return JSONResponse(status_code=401, content={"detail": str(exc)})

    try:
        count = await annotation_service.clear_annotations(
            project_id=str(project_id),
            user_id=str(user_id),
            session=write_session,
        )
        return MessageResponse(
            message=f"Cleared {count} annotations"
        )
    except LookupError as exc:
        return JSONResponse(status_code=404, content={"detail": str(exc)})
    except Exception as exc:
        logger.error("clear_annotations_failed", error=str(exc))
        return JSONResponse(
            status_code=500,
            content={"detail": "Failed to clear annotations"},
        )

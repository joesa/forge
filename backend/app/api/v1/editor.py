"""
Editor API routes (12 endpoints).

Handles: sessions CRUD, chat + apply, commands, WebSocket stream.
"""

from __future__ import annotations

import uuid

import structlog
from fastapi import APIRouter, Depends, Query, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_read_session, get_write_session
from app.services import editor_service
from app.schemas.editor import (
    ChatApplyRequest,
    ChatApplyResponse,
    ChatHistoryResponse,
    ChatMessageRequest,
    ChatMessageResponse,
    CommandRequest,
    CommandResponse,
    EditorSessionCreateRequest,
    EditorSessionResponse,
)

logger = structlog.get_logger()

router = APIRouter(prefix="/api/v1/editor", tags=["editor"])


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


# ── Sessions ─────────────────────────────────────────────────────────


@router.post("/sessions", response_model=EditorSessionResponse)
async def create_session(
    body: EditorSessionCreateRequest,
    request: Request,
    write_session: AsyncSession = Depends(get_write_session),
) -> EditorSessionResponse:
    """Create or resume an editor session."""
    try:
        user_id = _extract_user_id(request)
    except ValueError as exc:
        return JSONResponse(status_code=401, content={"detail": str(exc)})

    try:
        editor_session = await editor_service.create_or_resume_session(
            project_id=str(body.project_id),
            user_id=str(user_id),
            session=write_session,
        )
        return EditorSessionResponse(
            id=editor_session.id,
            project_id=editor_session.project_id,
            user_id=editor_session.user_id,
            is_active=editor_session.is_active,
            created_at=editor_session.created_at,
        )
    except LookupError as exc:
        return JSONResponse(status_code=404, content={"detail": str(exc)})
    except Exception as exc:
        logger.error("create_session_failed", error=str(exc))
        return JSONResponse(status_code=500, content={"detail": "Failed to create session"})


@router.get("/sessions/{session_id}", response_model=EditorSessionResponse)
async def get_session(
    session_id: uuid.UUID,
    request: Request,
    read_session: AsyncSession = Depends(get_read_session),
) -> EditorSessionResponse:
    """Get an editor session by ID."""
    try:
        user_id = _extract_user_id(request)
    except ValueError as exc:
        return JSONResponse(status_code=401, content={"detail": str(exc)})

    try:
        editor_session = await editor_service.get_session(
            session_id=str(session_id),
            user_id=str(user_id),
            session=read_session,
        )
        return EditorSessionResponse(
            id=editor_session.id,
            project_id=editor_session.project_id,
            user_id=editor_session.user_id,
            is_active=editor_session.is_active,
            created_at=editor_session.created_at,
        )
    except LookupError as exc:
        return JSONResponse(status_code=404, content={"detail": str(exc)})
    except Exception as exc:
        logger.error("get_session_failed", error=str(exc))
        return JSONResponse(status_code=500, content={"detail": "Failed to get session"})


@router.delete("/sessions/{session_id}")
async def close_session(
    session_id: uuid.UUID,
    request: Request,
    write_session: AsyncSession = Depends(get_write_session),
) -> JSONResponse:
    """Close an editor session."""
    try:
        user_id = _extract_user_id(request)
    except ValueError as exc:
        return JSONResponse(status_code=401, content={"detail": str(exc)})

    try:
        await editor_service.close_session(
            session_id=str(session_id),
            user_id=str(user_id),
            session=write_session,
        )
        return JSONResponse(content={"success": True})
    except LookupError as exc:
        return JSONResponse(status_code=404, content={"detail": str(exc)})
    except Exception as exc:
        logger.error("close_session_failed", error=str(exc))
        return JSONResponse(status_code=500, content={"detail": "Failed to close session"})


# ── Chat ─────────────────────────────────────────────────────────────


@router.get("/sessions/{session_id}/chat", response_model=ChatHistoryResponse)
async def get_chat_history(
    session_id: uuid.UUID,
    request: Request,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    read_session: AsyncSession = Depends(get_read_session),
) -> ChatHistoryResponse:
    """Get chat history for a session."""
    try:
        user_id = _extract_user_id(request)
    except ValueError as exc:
        return JSONResponse(status_code=401, content={"detail": str(exc)})

    try:
        messages, has_more = await editor_service.get_chat_history(
            session_id=str(session_id),
            user_id=str(user_id),
            limit=limit,
            offset=offset,
            session=read_session,
        )
        return ChatHistoryResponse(
            messages=[ChatMessageResponse(
                id=m.id,
                session_id=m.project_id,
                role=m.role.value if hasattr(m.role, 'value') else str(m.role),
                content=m.content,
                created_at=m.created_at,
            ) for m in messages],
            has_more=has_more,
        )
    except LookupError as exc:
        return JSONResponse(status_code=404, content={"detail": str(exc)})
    except Exception as exc:
        logger.error("get_chat_history_failed", error=str(exc))
        return JSONResponse(status_code=500, content={"detail": "Failed to get chat history"})


@router.post("/sessions/{session_id}/chat", response_model=ChatMessageResponse)
async def send_chat_message(
    session_id: uuid.UUID,
    body: ChatMessageRequest,
    request: Request,
    write_session: AsyncSession = Depends(get_write_session),
) -> ChatMessageResponse:
    """Send a chat message and get AI response."""
    try:
        user_id = _extract_user_id(request)
    except ValueError as exc:
        return JSONResponse(status_code=401, content={"detail": str(exc)})

    try:
        msg = await editor_service.send_chat_message(
            session_id=str(session_id),
            user_id=str(user_id),
            message=body.message,
            context_files=body.context_files,
            session=write_session,
        )
        return ChatMessageResponse(
            id=msg.id,
            session_id=msg.project_id,
            role=msg.role.value if hasattr(msg.role, 'value') else str(msg.role),
            content=msg.content,
            created_at=msg.created_at,
        )
    except LookupError as exc:
        return JSONResponse(status_code=404, content={"detail": str(exc)})
    except Exception as exc:
        logger.error("send_chat_failed", error=str(exc))
        return JSONResponse(status_code=500, content={"detail": "Failed to send message"})


@router.post("/sessions/{session_id}/chat/apply", response_model=ChatApplyResponse)
async def apply_code_block(
    session_id: uuid.UUID,
    body: ChatApplyRequest,
    request: Request,
    write_session: AsyncSession = Depends(get_write_session),
) -> ChatApplyResponse:
    """Apply a code block from a chat message to project files."""
    try:
        user_id = _extract_user_id(request)
    except ValueError as exc:
        return JSONResponse(status_code=401, content={"detail": str(exc)})

    try:
        files = await editor_service.apply_code_block(
            session_id=str(session_id),
            user_id=str(user_id),
            message_id=str(body.message_id),
            code_block_index=body.code_block_index,
            session=write_session,
        )
        return ChatApplyResponse(files_modified=files)
    except LookupError as exc:
        return JSONResponse(status_code=404, content={"detail": str(exc)})
    except Exception as exc:
        logger.error("apply_code_failed", error=str(exc))
        return JSONResponse(status_code=500, content={"detail": "Failed to apply code"})


# ── Commands ─────────────────────────────────────────────────────────


@router.post("/sessions/{session_id}/command", response_model=CommandResponse)
async def execute_command(
    session_id: uuid.UUID,
    body: CommandRequest,
    request: Request,
    write_session: AsyncSession = Depends(get_write_session),
) -> CommandResponse:
    """Execute a command in the sandbox (build, deploy, test, etc)."""
    try:
        user_id = _extract_user_id(request)
    except ValueError as exc:
        return JSONResponse(status_code=401, content={"detail": str(exc)})

    try:
        command_id = await editor_service.execute_command(
            session_id=str(session_id),
            user_id=str(user_id),
            command=body.command,
            args=body.args,
            session=write_session,
        )
        return CommandResponse(
            command_id=command_id,
            command=body.command,
        )
    except LookupError as exc:
        return JSONResponse(status_code=404, content={"detail": str(exc)})
    except Exception as exc:
        logger.error("execute_command_failed", error=str(exc))
        return JSONResponse(status_code=500, content={"detail": "Failed to execute command"})


# ── WebSocket Stream ─────────────────────────────────────────────────


@router.websocket("/sessions/{session_id}/stream")
async def editor_stream(
    websocket: WebSocket,
    session_id: uuid.UUID,
) -> None:
    """WebSocket stream for real-time editor events (file changes, command output, etc)."""
    await websocket.accept()
    logger.info("editor_ws_connected", session_id=str(session_id))

    try:
        while True:
            data = await websocket.receive_text()
            # Echo heartbeat for now — will be replaced with Redis pub/sub
            await websocket.send_json({"type": "heartbeat", "session_id": str(session_id)})
    except WebSocketDisconnect:
        logger.info("editor_ws_disconnected", session_id=str(session_id))

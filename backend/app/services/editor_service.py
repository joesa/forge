"""
Editor service — session management, AI chat, command execution.

Handles the core editor lifecycle:
  1. Create/resume sessions
  2. Chat with AI (context-aware, file-referencing)
  3. Apply code blocks from chat
  4. Execute commands (build, deploy, test, lint, install)
"""

from __future__ import annotations

import uuid

import structlog
from sqlalchemy import select, update as sa_update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chat_message import ChatMessage
from app.models.editor_session import EditorSession
from app.models.project import Project

logger = structlog.get_logger()


# ── Sessions ─────────────────────────────────────────────────────────


async def create_or_resume_session(
    project_id: str,
    user_id: str,
    session: AsyncSession,
) -> EditorSession:
    """Create a new editor session or resume the active one."""
    # Check for existing active session
    stmt = select(EditorSession).where(
        EditorSession.project_id == uuid.UUID(project_id),
        EditorSession.user_id == uuid.UUID(user_id),
        EditorSession.is_active.is_(True),
    )
    result = await session.execute(stmt)
    existing = result.scalar_one_or_none()

    if existing:
        logger.info("editor_session_resumed", session_id=str(existing.id))
        return existing

    # Verify project ownership
    await _verify_project_ownership(project_id, user_id, session)

    editor_session = EditorSession(
        project_id=uuid.UUID(project_id),
        user_id=uuid.UUID(user_id),
    )
    session.add(editor_session)
    await session.flush()

    logger.info("editor_session_created", session_id=str(editor_session.id))
    return editor_session


async def get_session(
    session_id: str,
    user_id: str,
    session: AsyncSession,
) -> EditorSession:
    """Get an editor session by ID."""
    return await _verify_session_ownership(session_id, user_id, session)


async def close_session(
    session_id: str,
    user_id: str,
    session: AsyncSession,
) -> None:
    """Close an editor session."""
    editor_session = await _verify_session_ownership(session_id, user_id, session)
    await session.execute(
        sa_update(EditorSession)
        .where(EditorSession.id == editor_session.id)
        .values(is_active=False)
    )
    await session.flush()
    logger.info("editor_session_closed", session_id=session_id)


# ── Chat ─────────────────────────────────────────────────────────────


async def get_chat_history(
    session_id: str,
    user_id: str,
    limit: int,
    offset: int,
    session: AsyncSession,
) -> tuple[list[ChatMessage], bool]:
    """Get chat messages for a session's project."""
    editor_session = await _verify_session_ownership(session_id, user_id, session)

    stmt = (
        select(ChatMessage)
        .where(
            ChatMessage.project_id == editor_session.project_id,
            ChatMessage.user_id == uuid.UUID(user_id),
        )
        .order_by(ChatMessage.created_at.desc())
        .limit(limit + 1)
        .offset(offset)
    )
    result = await session.execute(stmt)
    messages = list(result.scalars().all())

    has_more = len(messages) > limit
    if has_more:
        messages = messages[:limit]

    return list(reversed(messages)), has_more


async def send_chat_message(
    session_id: str,
    user_id: str,
    message: str,
    context_files: list[str],
    session: AsyncSession,
) -> ChatMessage:
    """Send a chat message and get AI response."""
    editor_session = await _verify_session_ownership(session_id, user_id, session)

    # Store user message
    user_msg = ChatMessage(
        project_id=editor_session.project_id,
        user_id=uuid.UUID(user_id),
        role="user",
        content=message,
    )
    session.add(user_msg)
    await session.flush()

    # AI response will be streamed via SSE in the route handler
    # For now, create a placeholder assistant message
    assistant_msg = ChatMessage(
        project_id=editor_session.project_id,
        user_id=uuid.UUID(user_id),
        role="assistant",
        content="I'll help you with that. Let me analyze the code...",
    )
    session.add(assistant_msg)
    await session.flush()

    logger.info(
        "chat_message_sent",
        session_id=session_id,
        user_id=user_id,
        message_length=len(message),
    )
    return assistant_msg


async def apply_code_block(
    session_id: str,
    user_id: str,
    message_id: str,
    code_block_index: int,
    session: AsyncSession,
) -> list[str]:
    """Apply a code block from a chat message to the project files."""
    editor_session = await _verify_session_ownership(session_id, user_id, session)

    # Verify message belongs to session's project
    stmt = select(ChatMessage).where(
        ChatMessage.id == uuid.UUID(message_id),
        ChatMessage.project_id == editor_session.project_id,
        ChatMessage.user_id == uuid.UUID(user_id),
    )
    result = await session.execute(stmt)
    chat_msg = result.scalar_one_or_none()
    if chat_msg is None:
        raise LookupError(f"Chat message {message_id} not found")

    # Parse code blocks and apply — stub for now
    logger.info(
        "code_block_applied",
        session_id=session_id,
        message_id=message_id,
        block_index=code_block_index,
    )
    return []  # list of modified file paths


# ── Commands ─────────────────────────────────────────────────────────


async def execute_command(
    session_id: str,
    user_id: str,
    command: str,
    args: dict[str, str],
    session: AsyncSession,
) -> uuid.UUID:
    """Queue a command for execution in the sandbox."""
    await _verify_session_ownership(session_id, user_id, session)

    command_id = uuid.uuid4()
    logger.info(
        "command_queued",
        session_id=session_id,
        command=command,
        command_id=str(command_id),
    )

    # Command execution will be handled by sandbox_service
    # and streamed via WebSocket

    return command_id


# ── Helpers ──────────────────────────────────────────────────────────


async def _verify_project_ownership(
    project_id: str,
    user_id: str,
    db: AsyncSession,
) -> Project:
    """Verify user owns the project."""
    stmt = select(Project).where(
        Project.id == uuid.UUID(project_id),
        Project.user_id == uuid.UUID(user_id),
    )
    result = await db.execute(stmt)
    project = result.scalar_one_or_none()
    if project is None:
        raise LookupError(f"Project {project_id} not found or access denied")
    return project


async def _verify_session_ownership(
    session_id: str,
    user_id: str,
    db: AsyncSession,
) -> EditorSession:
    """Verify user owns the editor session."""
    stmt = select(EditorSession).where(
        EditorSession.id == uuid.UUID(session_id),
        EditorSession.user_id == uuid.UUID(user_id),
    )
    result = await db.execute(stmt)
    editor_session = result.scalar_one_or_none()
    if editor_session is None:
        raise LookupError(f"Editor session {session_id} not found or access denied")
    return editor_session

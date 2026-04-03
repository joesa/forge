"""
Pydantic v2 schemas for editor endpoints.

All request/response bodies live here — never raw dicts in routes.
"""

from __future__ import annotations

import datetime
import uuid

from pydantic import BaseModel, Field


# ── Sessions ─────────────────────────────────────────────────────────


class EditorSessionCreateRequest(BaseModel):
    """POST /api/v1/editor/sessions body."""

    project_id: uuid.UUID


class EditorSessionResponse(BaseModel):
    """Single editor session."""

    id: uuid.UUID
    project_id: uuid.UUID
    user_id: uuid.UUID
    is_active: bool = True
    last_file_path: str | None = None
    cursor_position: dict[str, int] | None = None
    created_at: datetime.datetime

    model_config = {"from_attributes": True}


# ── Chat ─────────────────────────────────────────────────────────────


class ChatMessageRequest(BaseModel):
    """POST /api/v1/editor/sessions/{id}/chat body."""

    message: str = Field(min_length=1, max_length=16384)
    context_files: list[str] = Field(
        default_factory=list,
        description="File paths to include as context",
    )
    annotations: list[uuid.UUID] = Field(
        default_factory=list,
        description="Annotation IDs to include as context",
    )


class ChatMessageResponse(BaseModel):
    """Single chat message."""

    id: uuid.UUID
    session_id: uuid.UUID
    role: str = Field(description="user | assistant | system")
    content: str
    files_referenced: list[str] = Field(default_factory=list)
    has_code_blocks: bool = False
    created_at: datetime.datetime

    model_config = {"from_attributes": True}


class ChatHistoryResponse(BaseModel):
    """GET /api/v1/editor/sessions/{id}/chat response."""

    messages: list[ChatMessageResponse]
    has_more: bool = False


class ChatApplyRequest(BaseModel):
    """POST /api/v1/editor/sessions/{id}/chat/apply body."""

    message_id: uuid.UUID
    code_block_index: int = Field(ge=0, le=50)


class ChatApplyResponse(BaseModel):
    """Response after applying a code block from chat."""

    files_modified: list[str]
    success: bool = True


# ── Commands ─────────────────────────────────────────────────────────


class CommandRequest(BaseModel):
    """POST /api/v1/editor/sessions/{id}/command body."""

    command: str = Field(
        min_length=1,
        max_length=64,
        description="build | deploy | run-tests | lint | install-deps",
    )
    args: dict[str, str] = Field(default_factory=dict)


class CommandResponse(BaseModel):
    """Immediate acknowledgement of command submission."""

    command_id: uuid.UUID
    command: str
    status: str = "queued"
    message: str = "Command submitted"

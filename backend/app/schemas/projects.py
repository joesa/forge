"""
Pydantic v2 schemas for project endpoints.

All request/response bodies live here — never raw dicts in routes.
"""

import datetime
import uuid

from pydantic import BaseModel, Field


# ── Request schemas ──────────────────────────────────────────────────


class ProjectCreateRequest(BaseModel):
    """POST /api/v1/projects body."""

    name: str = Field(min_length=1, max_length=256)
    description: str | None = Field(default=None, max_length=4096)
    framework: str | None = Field(
        default=None,
        description="One of: nextjs, react_vite, remix, fastapi_react",
    )


class ProjectUpdateRequest(BaseModel):
    """PUT /api/v1/projects/{id} body."""

    name: str | None = Field(default=None, min_length=1, max_length=256)
    description: str | None = Field(default=None, max_length=4096)
    status: str | None = Field(
        default=None,
        description="One of: draft, building, live, error",
    )
    framework: str | None = Field(
        default=None,
        description="One of: nextjs, react_vite, remix, fastapi_react",
    )


class FileSaveRequest(BaseModel):
    """PUT /api/v1/projects/{id}/files/content body."""

    path: str = Field(min_length=1, max_length=1024)
    content: str


class FileRenameRequest(BaseModel):
    """POST /api/v1/projects/{id}/files/rename body."""

    old_path: str = Field(min_length=1, max_length=1024)
    new_path: str = Field(min_length=1, max_length=1024)


# ── Response schemas ─────────────────────────────────────────────────


class ProjectResponse(BaseModel):
    """Single project representation."""

    id: uuid.UUID
    user_id: uuid.UUID
    name: str
    description: str | None = None
    status: str
    framework: str | None = None
    created_at: datetime.datetime
    updated_at: datetime.datetime

    model_config = {"from_attributes": True}


class ProjectListResponse(BaseModel):
    """List of projects."""

    items: list[ProjectResponse]
    count: int


class FileTreeNode(BaseModel):
    """A node in the project file tree."""

    name: str
    path: str
    type: str = Field(description="'file' or 'directory'")
    children: list["FileTreeNode"] | None = None


class FileTreeResponse(BaseModel):
    """Project file tree."""

    project_id: uuid.UUID
    tree: list[FileTreeNode]


class FileContentResponse(BaseModel):
    """File content response."""

    project_id: uuid.UUID
    path: str
    content: str


class MessageResponse(BaseModel):
    """Generic success message."""

    message: str

"""
Pydantic v2 schemas for preview system endpoints.

All request/response bodies live here — never raw dicts in routes.
"""

import datetime
import uuid

from pydantic import BaseModel, Field, field_validator


# ── Preview URL ──────────────────────────────────────────────────────


class PreviewURLResult(BaseModel):
    """GET /api/v1/sandbox/{id}/preview-url response."""

    url: str
    ready: bool
    expires_at: datetime.datetime | None = None


# ── Health Check ─────────────────────────────────────────────────────


class HealthResult(BaseModel):
    """GET /api/v1/sandbox/{id}/preview/health response."""

    healthy: bool
    latency_ms: int
    last_checked: datetime.datetime


# ── Screenshots ──────────────────────────────────────────────────────


class ScreenshotRequest(BaseModel):
    """POST /api/v1/sandbox/{id}/preview/screenshot body."""

    route: str = Field(default="/", max_length=512)
    width: int = Field(default=1280, ge=320, le=3840)
    height: int = Field(default=800, ge=240, le=2160)


class ScreenshotResult(BaseModel):
    """POST /api/v1/sandbox/{id}/preview/screenshot response."""

    screenshot_url: str
    taken_at: datetime.datetime


# ── Share ────────────────────────────────────────────────────────────


class ShareRequest(BaseModel):
    """POST /api/v1/sandbox/{id}/preview/share body."""

    expires_hours: int = Field(default=24, ge=1, le=720)


class ShareResult(BaseModel):
    """POST /api/v1/sandbox/{id}/preview/share response."""

    share_url: str
    token: str
    expires_at: datetime.datetime


# ── Annotations ──────────────────────────────────────────────────────


class AnnotationCreateRequest(BaseModel):
    """POST /api/v1/projects/{id}/annotations body."""

    session_id: str = Field(min_length=1, max_length=256)
    css_selector: str = Field(min_length=1, max_length=1024)
    route: str = Field(min_length=1, max_length=512)
    comment: str = Field(min_length=1, max_length=4096)
    x_pct: float = Field(ge=0.0, le=1.0)
    y_pct: float = Field(ge=0.0, le=1.0)

    @field_validator("x_pct", "y_pct")
    @classmethod
    def validate_percentage(cls, v: float) -> float:
        """Ensure percentage values are within [0.0, 1.0]."""
        if not 0.0 <= v <= 1.0:
            raise ValueError("Percentage must be between 0.0 and 1.0")
        return round(v, 6)


class AnnotationResponse(BaseModel):
    """Single annotation representation."""

    id: uuid.UUID
    project_id: uuid.UUID
    user_id: uuid.UUID
    x_pct: float
    y_pct: float
    page_route: str | None = None
    css_selector: str | None = None
    session_id: str | None = None
    content: str
    resolved: bool
    created_at: datetime.datetime
    updated_at: datetime.datetime

    model_config = {"from_attributes": True}


class AnnotationListResponse(BaseModel):
    """List of annotations."""

    items: list[AnnotationResponse]
    count: int


class AnnotationAIContextResponse(BaseModel):
    """Formatted annotation context for AI prompt injection."""

    context_text: str


# ── Snapshots ────────────────────────────────────────────────────────


class SnapshotResponse(BaseModel):
    """Single build snapshot."""

    id: uuid.UUID
    build_id: uuid.UUID
    project_id: uuid.UUID
    snapshot_index: int
    label: str | None = None
    screenshot_url: str | None = None
    created_at: datetime.datetime

    model_config = {"from_attributes": True}


class SnapshotListResponse(BaseModel):
    """List of snapshots."""

    items: list[SnapshotResponse]
    count: int


# ── File Sync ────────────────────────────────────────────────────────


class FileSyncRequest(BaseModel):
    """Request body for file sync (internally used)."""

    file_path: str = Field(min_length=1, max_length=1024)
    content: str = Field(max_length=10_485_760)  # 10 MB cap


# ── Generic ──────────────────────────────────────────────────────────


class MessageResponse(BaseModel):
    """Generic success message."""

    message: str

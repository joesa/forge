"""
Pydantic v2 schemas for build endpoints.

All request/response bodies live here — never raw dicts in routes.
"""

from __future__ import annotations

import datetime
import uuid

from pydantic import BaseModel, Field


# ── Request schemas ──────────────────────────────────────────────────


class BuildStartRequest(BaseModel):
    """POST /api/v1/build/start body."""

    project_id: uuid.UUID
    pipeline_id: uuid.UUID | None = None
    incremental: bool = False


class BuildRetryRequest(BaseModel):
    """POST /api/v1/build/{id}/retry body."""

    from_agent: int | None = Field(
        default=None, ge=1, le=10,
        description="Resume from specific agent (1-10)",
    )


class BuildCancelRequest(BaseModel):
    """POST /api/v1/build/{id}/cancel body."""

    reason: str | None = Field(default=None, max_length=512)


# ── Response schemas ─────────────────────────────────────────────────


class BuildResponse(BaseModel):
    """Single build representation."""

    id: uuid.UUID
    project_id: uuid.UUID
    pipeline_id: uuid.UUID | None = None
    status: str
    current_agent: int | None = None
    current_agent_name: str | None = None
    total_agents: int = 10
    errors: list[str] = Field(default_factory=list)
    started_at: datetime.datetime | None = None
    completed_at: datetime.datetime | None = None
    created_at: datetime.datetime

    model_config = {"from_attributes": True}


class BuildListResponse(BaseModel):
    """GET /api/v1/build?project_id= response."""

    builds: list[BuildResponse]
    total: int = 0


class BuildLogEntry(BaseModel):
    """Single log line from a build."""

    timestamp: datetime.datetime
    level: str = "info"
    agent: str | None = None
    message: str


class BuildLogsResponse(BaseModel):
    """GET /api/v1/build/{id}/logs response."""

    build_id: uuid.UUID
    logs: list[BuildLogEntry]
    has_more: bool = False

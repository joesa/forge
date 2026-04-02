"""
Pydantic v2 schemas for pipeline endpoints.

All request/response bodies live here — never raw dicts in routes.
"""

from __future__ import annotations

import datetime
import uuid

from pydantic import BaseModel, Field


# ── Request schemas ──────────────────────────────────────────────────


class IdeaSpecInput(BaseModel):
    """The user's idea specification — input to the pipeline."""

    title: str = Field(min_length=1, max_length=256)
    description: str = Field(min_length=1, max_length=8192)
    features: list[str] = Field(default_factory=list)
    framework: str | None = Field(
        default=None,
        description="One of: nextjs, react_vite, remix, fastapi_react",
    )
    target_audience: str | None = Field(default=None, max_length=1024)


class PipelineRunRequest(BaseModel):
    """POST /api/v1/pipeline/run body."""

    project_id: uuid.UUID
    idea_spec: IdeaSpecInput


# ── Response schemas ─────────────────────────────────────────────────


class PipelineRunResponse(BaseModel):
    """Returned immediately from POST /run — non-blocking."""

    pipeline_id: uuid.UUID
    status: str = "queued"
    message: str = "Pipeline submitted successfully"


class GateResultResponse(BaseModel):
    """Single gate check result."""

    gate_id: str
    passed: bool
    reason: str


class StageInfo(BaseModel):
    """Information about a single pipeline stage."""

    stage: int
    name: str
    status: str  # "pending" | "running" | "completed" | "failed"
    gates: list[GateResultResponse] = Field(default_factory=list)


class PipelineStatusResponse(BaseModel):
    """GET /api/v1/pipeline/{id}/status response."""

    pipeline_id: uuid.UUID
    project_id: uuid.UUID
    status: str
    current_stage: int
    started_at: datetime.datetime | None = None
    completed_at: datetime.datetime | None = None
    errors: list[str] = Field(default_factory=list)
    created_at: datetime.datetime

    model_config = {"from_attributes": True}


class PipelineStageResponse(BaseModel):
    """GET /api/v1/pipeline/{id}/stages response."""

    pipeline_id: uuid.UUID
    stages: list[StageInfo]
    gate_results: dict[str, GateResultResponse] = Field(default_factory=dict)

"""
Pydantic v2 schemas for settings endpoints.

All request/response bodies live here — never raw dicts in routes.
"""

from __future__ import annotations

import datetime
import uuid

from pydantic import BaseModel, Field


# ── Profile ──────────────────────────────────────────────────────────


class ProfileUpdateRequest(BaseModel):
    """PUT /api/v1/settings/profile body."""

    display_name: str | None = Field(default=None, min_length=1, max_length=128)
    avatar_url: str | None = Field(default=None, max_length=2048)
    timezone: str | None = Field(default=None, max_length=64)


class ProfileResponse(BaseModel):
    """GET /api/v1/settings/profile response."""

    id: uuid.UUID
    email: str
    display_name: str | None = None
    avatar_url: str | None = None
    timezone: str | None = None
    plan: str = "free"
    onboarded: bool = False
    created_at: datetime.datetime

    model_config = {"from_attributes": True}


# ── AI Providers ─────────────────────────────────────────────────────


class AIProviderCreateRequest(BaseModel):
    """POST /api/v1/settings/ai-providers body."""

    provider_name: str = Field(min_length=1, max_length=64)
    api_key: str = Field(min_length=1, max_length=512)
    base_url: str | None = Field(default=None, max_length=2048)


class AIProviderUpdateRequest(BaseModel):
    """PUT /api/v1/settings/ai-providers/{id} body."""

    api_key: str | None = Field(default=None, min_length=1, max_length=512)
    base_url: str | None = Field(default=None, max_length=2048)
    is_enabled: bool | None = None


class AIProviderResponse(BaseModel):
    """Single AI provider (key masked)."""

    id: uuid.UUID
    provider_name: str
    is_enabled: bool = True
    is_connected: bool = False
    base_url: str | None = None
    key_last_four: str | None = None
    created_at: datetime.datetime

    model_config = {"from_attributes": True}


class AIProviderTestResponse(BaseModel):
    """POST /api/v1/settings/ai-providers/{id}/test response."""

    provider_name: str
    connected: bool
    latency_ms: int | None = None
    models_available: list[str] = Field(default_factory=list)
    error: str | None = None


# ── Model Routing ────────────────────────────────────────────────────


class ModelRoutingRule(BaseModel):
    """A single routing rule: stage → provider → model."""

    stage: str = Field(min_length=1, max_length=64)
    provider: str = Field(min_length=1, max_length=64)
    model: str = Field(min_length=1, max_length=128)
    fallback_provider: str | None = Field(default=None, max_length=64)
    fallback_model: str | None = Field(default=None, max_length=128)


class ModelRoutingUpdateRequest(BaseModel):
    """PUT /api/v1/settings/model-routing body."""

    rules: list[ModelRoutingRule] = Field(min_length=1)


class ModelRoutingResponse(BaseModel):
    """GET /api/v1/settings/model-routing response."""

    rules: list[ModelRoutingRule]
    estimated_cost_per_pipeline: float | None = None


# ── API Keys ─────────────────────────────────────────────────────────


class APIKeyCreateRequest(BaseModel):
    """POST /api/v1/settings/api-keys body."""

    name: str = Field(min_length=1, max_length=128)
    expires_in_days: int | None = Field(default=None, ge=1, le=365)


class APIKeyCreateResponse(BaseModel):
    """Returned once — contains the raw API key. Never shown again."""

    id: uuid.UUID
    name: str
    key: str  # raw key, shown ONCE
    prefix: str
    expires_at: datetime.datetime | None = None
    created_at: datetime.datetime


class APIKeyResponse(BaseModel):
    """Public API key representation (no raw key)."""

    id: uuid.UUID
    name: str
    prefix: str
    last_used_at: datetime.datetime | None = None
    expires_at: datetime.datetime | None = None
    created_at: datetime.datetime

    model_config = {"from_attributes": True}


# ── Integrations ─────────────────────────────────────────────────────


class IntegrationConnectRequest(BaseModel):
    """POST /api/v1/settings/integrations/{service}/connect body."""

    code: str = Field(min_length=1, max_length=2048, description="OAuth code")
    redirect_uri: str | None = Field(default=None, max_length=2048)


class IntegrationResponse(BaseModel):
    """Single integration status."""

    service: str
    connected: bool = False
    username: str | None = None
    connected_at: datetime.datetime | None = None

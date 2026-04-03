"""
AI API routes (2 endpoints).

Returns available providers and models — reads from configuration.
"""

from __future__ import annotations

import structlog
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
import uuid

logger = structlog.get_logger()

router = APIRouter(prefix="/api/v1/ai", tags=["ai"])


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


# ── Schemas ──────────────────────────────────────────────────────────

SUPPORTED_PROVIDERS = {
    "anthropic": {
        "name": "Anthropic",
        "models": [
            "claude-opus-4-20250514", "claude-sonnet-4-20250514", "claude-haiku-4-20250514",
        ],
    },
    "openai": {
        "name": "OpenAI",
        "models": ["gpt-4o", "gpt-4o-mini", "o1", "o3"],
    },
    "google": {
        "name": "Google",
        "models": ["gemini-ultra", "gemini-1.5-pro", "gemini-1.5-flash"],
    },
    "xai": {
        "name": "xAI",
        "models": ["grok-2", "grok-2-mini"],
    },
    "mistral": {
        "name": "Mistral",
        "models": ["mistral-large", "mistral-medium", "mistral-small"],
    },
    "cohere": {
        "name": "Cohere",
        "models": ["command-r-plus"],
    },
    "deepseek": {
        "name": "DeepSeek",
        "models": ["deepseek-v3", "deepseek-r1"],
    },
    "together": {
        "name": "Together AI",
        "models": ["llama-3.3-70b"],
    },
}


class ProviderInfo(BaseModel):
    """AI provider info."""

    id: str
    name: str
    model_count: int


class ModelInfo(BaseModel):
    """AI model info."""

    id: str
    provider: str
    context_window: int = 128000


class ProvidersResponse(BaseModel):
    """GET /api/v1/ai/providers response."""

    providers: list[ProviderInfo]


class ModelsResponse(BaseModel):
    """GET /api/v1/ai/providers/{id}/models response."""

    provider: str
    models: list[ModelInfo]


# ── Endpoints ────────────────────────────────────────────────────────


@router.get("/providers", response_model=ProvidersResponse)
async def list_providers(request: Request) -> ProvidersResponse:
    """List all supported AI providers."""
    try:
        _extract_user_id(request)
    except ValueError:
        return JSONResponse(status_code=401, content={"detail": "Unauthorized"})

    providers = [
        ProviderInfo(
            id=pid,
            name=info["name"],
            model_count=len(info["models"]),
        )
        for pid, info in SUPPORTED_PROVIDERS.items()
    ]
    return ProvidersResponse(providers=providers)


@router.get("/providers/{provider_id}/models", response_model=ModelsResponse)
async def list_models(
    provider_id: str,
    request: Request,
) -> ModelsResponse:
    """List all models for a provider."""
    try:
        _extract_user_id(request)
    except ValueError:
        return JSONResponse(status_code=401, content={"detail": "Unauthorized"})

    info = SUPPORTED_PROVIDERS.get(provider_id)
    if info is None:
        return JSONResponse(status_code=404, content={"detail": f"Provider '{provider_id}' not found"})

    models = [
        ModelInfo(id=m, provider=provider_id)
        for m in info["models"]
    ]
    return ModelsResponse(provider=provider_id, models=models)

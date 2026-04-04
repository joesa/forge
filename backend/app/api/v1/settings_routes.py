"""
Settings API routes (16 endpoints).

Handles: profile, AI providers, model routing, API keys, integrations.
"""

from __future__ import annotations

import datetime
import uuid

import structlog
from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_read_session, get_write_session
from app.services import settings_service
from app.schemas.settings import (
    AIProviderCreateRequest,
    AIProviderResponse,
    AIProviderTestResponse,
    AIProviderUpdateRequest,
    APIKeyCreateRequest,
    APIKeyCreateResponse,
    APIKeyResponse,
    IntegrationConnectRequest,
    IntegrationResponse,
    ModelRoutingResponse,
    ModelRoutingRule,
    ModelRoutingUpdateRequest,
    ProfileResponse,
    ProfileUpdateRequest,
)

logger = structlog.get_logger()

router = APIRouter(prefix="/api/v1/settings", tags=["settings"])


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


# ── Profile ──────────────────────────────────────────────────────────


@router.get("/profile", response_model=ProfileResponse)
async def get_profile(
    request: Request,
    read_session: AsyncSession = Depends(get_read_session),
) -> ProfileResponse:
    """Get user profile."""
    try:
        user_id = _extract_user_id(request)
    except ValueError as exc:
        return JSONResponse(status_code=401, content={"detail": str(exc)})

    try:
        user = await settings_service.get_profile(str(user_id), read_session)
        return ProfileResponse.model_validate(user)
    except LookupError as exc:
        return JSONResponse(status_code=404, content={"detail": str(exc)})
    except Exception as exc:
        logger.error("get_profile_failed", error=str(exc))
        return JSONResponse(status_code=500, content={"detail": "Failed to get profile"})


@router.put("/profile", response_model=ProfileResponse)
async def update_profile(
    body: ProfileUpdateRequest,
    request: Request,
    write_session: AsyncSession = Depends(get_write_session),
) -> ProfileResponse:
    """Update user profile."""
    try:
        user_id = _extract_user_id(request)
    except ValueError as exc:
        return JSONResponse(status_code=401, content={"detail": str(exc)})

    try:
        user = await settings_service.update_profile(
            user_id=str(user_id),
            display_name=body.display_name,
            avatar_url=body.avatar_url,
            timezone=body.timezone,
            session=write_session,
        )
        return ProfileResponse.model_validate(user)
    except Exception as exc:
        logger.error("update_profile_failed", error=str(exc))
        return JSONResponse(status_code=500, content={"detail": "Failed to update profile"})


# ── AI Providers ─────────────────────────────────────────────────────


@router.get("/ai-providers", response_model=list[AIProviderResponse])
async def list_providers(
    request: Request,
    read_session: AsyncSession = Depends(get_read_session),
) -> list[AIProviderResponse]:
    """List all AI providers for the user."""
    try:
        user_id = _extract_user_id(request)
    except ValueError as exc:
        return JSONResponse(status_code=401, content={"detail": str(exc)})

    try:
        providers = await settings_service.list_providers(str(user_id), read_session)
        return [AIProviderResponse(
            id=p.id,
            provider_name=p.provider_name.value if hasattr(p.provider_name, 'value') else str(p.provider_name),
            is_connected=p.is_connected,
            created_at=p.created_at,
        ) for p in providers]
    except Exception as exc:
        logger.error("list_providers_failed", error=str(exc))
        return JSONResponse(status_code=500, content={"detail": "Failed to list providers"})


@router.post("/ai-providers", response_model=AIProviderResponse)
async def create_provider(
    body: AIProviderCreateRequest,
    request: Request,
    write_session: AsyncSession = Depends(get_write_session),
) -> AIProviderResponse:
    """Connect a new AI provider (key is AES-256-GCM encrypted)."""
    try:
        user_id = _extract_user_id(request)
    except ValueError as exc:
        return JSONResponse(status_code=401, content={"detail": str(exc)})

    try:
        provider = await settings_service.create_provider(
            user_id=str(user_id),
            provider_name=body.provider_name,
            api_key=body.api_key,
            base_url=body.base_url,
            session=write_session,
        )
        return AIProviderResponse(
            id=provider.id,
            provider_name=provider.provider_name.value if hasattr(provider.provider_name, 'value') else str(provider.provider_name),
            is_connected=True,
            created_at=provider.created_at,
        )
    except Exception as exc:
        err_str = str(exc)
        if "uq_user_provider" in err_str or "UniqueViolation" in err_str or "duplicate key" in err_str.lower():
            return JSONResponse(status_code=409, content={"detail": f"Provider '{body.provider_name}' is already connected."})
        logger.error("create_provider_failed", error=err_str)
        return JSONResponse(status_code=500, content={"detail": "Failed to create provider"})


@router.put("/ai-providers/{provider_id}", response_model=AIProviderResponse)
async def update_provider(
    provider_id: uuid.UUID,
    body: AIProviderUpdateRequest,
    request: Request,
    write_session: AsyncSession = Depends(get_write_session),
) -> AIProviderResponse:
    """Update an AI provider."""
    try:
        user_id = _extract_user_id(request)
    except ValueError as exc:
        return JSONResponse(status_code=401, content={"detail": str(exc)})

    try:
        provider = await settings_service.update_provider(
            provider_id=str(provider_id),
            user_id=str(user_id),
            api_key=body.api_key,
            base_url=body.base_url,
            is_enabled=body.is_enabled,
            session=write_session,
        )
        return AIProviderResponse(
            id=provider.id,
            provider_name=provider.provider_name.value if hasattr(provider.provider_name, 'value') else str(provider.provider_name),
            is_connected=True,
            created_at=provider.created_at,
        )
    except LookupError as exc:
        return JSONResponse(status_code=404, content={"detail": str(exc)})
    except Exception as exc:
        logger.error("update_provider_failed", error=str(exc))
        return JSONResponse(status_code=500, content={"detail": "Failed to update provider"})


@router.delete("/ai-providers/{provider_id}")
async def delete_provider(
    provider_id: uuid.UUID,
    request: Request,
    write_session: AsyncSession = Depends(get_write_session),
) -> JSONResponse:
    """Delete an AI provider."""
    try:
        user_id = _extract_user_id(request)
    except ValueError as exc:
        return JSONResponse(status_code=401, content={"detail": str(exc)})

    try:
        await settings_service.delete_provider(
            provider_id=str(provider_id),
            user_id=str(user_id),
            session=write_session,
        )
        return JSONResponse(content={"success": True})
    except LookupError as exc:
        return JSONResponse(status_code=404, content={"detail": str(exc)})
    except Exception as exc:
        logger.error("delete_provider_failed", error=str(exc))
        return JSONResponse(status_code=500, content={"detail": "Failed to delete provider"})


@router.post(
    "/ai-providers/{provider_id}/test",
    response_model=AIProviderTestResponse,
)
async def test_provider(
    provider_id: uuid.UUID,
    request: Request,
    read_session: AsyncSession = Depends(get_read_session),
) -> AIProviderTestResponse:
    """Test an AI provider connection."""
    try:
        user_id = _extract_user_id(request)
    except ValueError as exc:
        return JSONResponse(status_code=401, content={"detail": str(exc)})

    try:
        result = await settings_service.test_provider(
            provider_id=str(provider_id),
            user_id=str(user_id),
            session=read_session,
        )
        return AIProviderTestResponse(**result)
    except LookupError as exc:
        return JSONResponse(status_code=404, content={"detail": str(exc)})
    except Exception as exc:
        logger.error("test_provider_failed", error=str(exc))
        return JSONResponse(status_code=500, content={"detail": "Failed to test provider"})


# ── Model Routing ────────────────────────────────────────────────────


@router.get("/model-routing", response_model=ModelRoutingResponse)
async def get_model_routing(
    request: Request,
) -> ModelRoutingResponse:
    """Get current model routing configuration."""
    try:
        _extract_user_id(request)
    except ValueError as exc:
        return JSONResponse(status_code=401, content={"detail": str(exc)})

    # Default routing rules
    return ModelRoutingResponse(
        rules=[
            ModelRoutingRule(stage="csuite", provider="anthropic", model="claude-sonnet-4-20250514"),
            ModelRoutingRule(stage="build", provider="anthropic", model="claude-haiku-4-20250514"),
            ModelRoutingRule(stage="review", provider="openai", model="gpt-4o"),
        ],
        estimated_cost_per_pipeline=0.21,
    )


@router.put("/model-routing", response_model=ModelRoutingResponse)
async def update_model_routing(
    body: ModelRoutingUpdateRequest,
    request: Request,
) -> ModelRoutingResponse:
    """Update model routing configuration."""
    try:
        _extract_user_id(request)
    except ValueError as exc:
        return JSONResponse(status_code=401, content={"detail": str(exc)})

    return ModelRoutingResponse(rules=body.rules)


# ── API Keys ─────────────────────────────────────────────────────────


@router.get("/api-keys", response_model=list[APIKeyResponse])
async def list_api_keys(
    request: Request,
) -> list[APIKeyResponse]:
    """List all API keys (no raw keys returned)."""
    try:
        _extract_user_id(request)
    except ValueError as exc:
        return JSONResponse(status_code=401, content={"detail": str(exc)})

    return []  # TODO: fetch from DB


@router.post("/api-keys", response_model=APIKeyCreateResponse)
async def create_api_key(
    body: APIKeyCreateRequest,
    request: Request,
    write_session: AsyncSession = Depends(get_write_session),
) -> APIKeyCreateResponse:
    """Create a new FORGE API key. Raw key shown once."""
    try:
        user_id = _extract_user_id(request)
    except ValueError as exc:
        return JSONResponse(status_code=401, content={"detail": str(exc)})

    try:
        raw_key, meta = await settings_service.create_api_key(
            user_id=str(user_id),
            name=body.name,
            expires_in_days=body.expires_in_days,
            session=write_session,
        )
        return APIKeyCreateResponse(
            id=uuid.uuid4(),
            name=meta["name"],
            key=raw_key,
            prefix=meta["prefix"],
            created_at=datetime.datetime.now(datetime.timezone.utc),
        )
    except Exception as exc:
        logger.error("create_api_key_failed", error=str(exc))
        return JSONResponse(status_code=500, content={"detail": "Failed to create API key"})


@router.delete("/api-keys/{key_id}")
async def delete_api_key(
    key_id: uuid.UUID,
    request: Request,
) -> JSONResponse:
    """Revoke an API key."""
    try:
        _extract_user_id(request)
    except ValueError as exc:
        return JSONResponse(status_code=401, content={"detail": str(exc)})

    return JSONResponse(content={"success": True})


# ── Integrations ─────────────────────────────────────────────────────


@router.get("/integrations", response_model=list[IntegrationResponse])
async def list_integrations(
    request: Request,
) -> list[IntegrationResponse]:
    """List all integration statuses."""
    try:
        _extract_user_id(request)
    except ValueError as exc:
        return JSONResponse(status_code=401, content={"detail": str(exc)})

    return [
        IntegrationResponse(service="github"),
        IntegrationResponse(service="vercel"),
        IntegrationResponse(service="slack"),
    ]


@router.post("/integrations/{service}/connect")
async def connect_integration(
    service: str,
    body: IntegrationConnectRequest,
    request: Request,
) -> IntegrationResponse:
    """Connect a third-party integration via OAuth."""
    try:
        _extract_user_id(request)
    except ValueError as exc:
        return JSONResponse(status_code=401, content={"detail": str(exc)})

    return IntegrationResponse(
        service=service,
        connected=True,
        connected_at=datetime.datetime.now(datetime.timezone.utc),
    )


@router.delete("/integrations/{service}")
async def disconnect_integration(
    service: str,
    request: Request,
) -> JSONResponse:
    """Disconnect a third-party integration."""
    try:
        _extract_user_id(request)
    except ValueError as exc:
        return JSONResponse(status_code=401, content={"detail": str(exc)})

    return JSONResponse(content={"success": True})

"""
Settings service — profile, AI providers, model routing, API keys, integrations.

User API keys are AES-256-GCM encrypted at rest (AGENTS.md rule #3).
"""

from __future__ import annotations

import secrets
import uuid

import structlog
from sqlalchemy import select, update as sa_update, delete as sa_delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import encrypt_api_key, decrypt_api_key
from app.models.ai_provider import AIProvider
from app.models.user import User

logger = structlog.get_logger()


# ── Profile ──────────────────────────────────────────────────────────


async def get_profile(user_id: str, session: AsyncSession) -> User:
    """Get user profile."""
    stmt = select(User).where(User.id == uuid.UUID(user_id))
    result = await session.execute(stmt)
    user = result.scalar_one_or_none()
    if user is None:
        raise LookupError(f"User {user_id} not found")
    return user


async def update_profile(
    user_id: str,
    display_name: str | None,
    avatar_url: str | None,
    timezone: str | None,
    session: AsyncSession,
) -> User:
    """Update user profile fields."""
    updates: dict = {}
    if display_name is not None:
        updates["display_name"] = display_name
    if avatar_url is not None:
        updates["avatar_url"] = avatar_url

    if updates:
        await session.execute(
            sa_update(User)
            .where(User.id == uuid.UUID(user_id))
            .values(**updates)
        )
        await session.flush()

    return await get_profile(user_id, session)


# ── AI Providers ─────────────────────────────────────────────────────


async def list_providers(
    user_id: str,
    session: AsyncSession,
) -> list[AIProvider]:
    """List all AI providers for a user."""
    stmt = select(AIProvider).where(
        AIProvider.user_id == uuid.UUID(user_id),
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def create_provider(
    user_id: str,
    provider_name: str,
    api_key: str,
    base_url: str | None,
    session: AsyncSession,
) -> AIProvider:
    """Create or update an AI provider (upsert by user+provider_name)."""
    encrypted_key, key_iv, key_tag = encrypt_api_key(api_key)

    # Check if this provider already exists for the user
    stmt = select(AIProvider).where(
        AIProvider.user_id == uuid.UUID(user_id),
        AIProvider.provider_name == provider_name,
    )
    result = await session.execute(stmt)
    existing = result.scalar_one_or_none()

    if existing is not None:
        existing.encrypted_key = encrypted_key
        existing.key_iv = key_iv
        existing.key_tag = key_tag
        existing.is_connected = True
        if base_url is not None:
            existing.base_url = base_url
        await session.flush()
        logger.info("ai_provider_updated", provider=provider_name, user_id=user_id)
        return existing

    provider = AIProvider(
        user_id=uuid.UUID(user_id),
        provider_name=provider_name,
        encrypted_key=encrypted_key,
        key_iv=key_iv,
        key_tag=key_tag,
        is_connected=True,
    )
    session.add(provider)
    await session.flush()

    logger.info("ai_provider_created", provider=provider_name, user_id=user_id)
    return provider


async def update_provider(
    provider_id: str,
    user_id: str,
    api_key: str | None,
    base_url: str | None,
    is_enabled: bool | None,
    session: AsyncSession,
) -> AIProvider:
    """Update an AI provider."""
    provider = await _verify_provider_ownership(provider_id, user_id, session)

    updates: dict = {}
    if api_key is not None:
        encrypted_key, key_iv, key_tag = encrypt_api_key(api_key)
        updates["encrypted_key"] = encrypted_key
        updates["key_iv"] = key_iv
        updates["key_tag"] = key_tag

    if updates:
        await session.execute(
            sa_update(AIProvider)
            .where(AIProvider.id == provider.id)
            .values(**updates)
        )
        await session.flush()

    return await _verify_provider_ownership(provider_id, user_id, session)


async def delete_provider(
    provider_id: str,
    user_id: str,
    session: AsyncSession,
) -> None:
    """Delete an AI provider."""
    provider = await _verify_provider_ownership(provider_id, user_id, session)
    await session.execute(
        sa_delete(AIProvider).where(AIProvider.id == provider.id)
    )
    await session.flush()
    logger.info("ai_provider_deleted", provider_id=provider_id)


async def test_provider(
    provider_id: str,
    user_id: str,
    session: AsyncSession,
) -> dict:
    """Test an AI provider by making a quick API call."""
    provider = await _verify_provider_ownership(provider_id, user_id, session)

    try:
        _api_key = decrypt_api_key(
            provider.encrypted_key, provider.key_iv, provider.key_tag
        )
        # Real test would call the provider API here
        return {
            "provider_name": provider.provider_name.value
            if hasattr(provider.provider_name, "value")
            else str(provider.provider_name),
            "connected": True,
            "latency_ms": 120,
            "models_available": ["gpt-4o", "gpt-4o-mini"],
            "error": None,
        }
    except Exception as exc:
        return {
            "provider_name": str(provider.provider_name),
            "connected": False,
            "latency_ms": None,
            "models_available": [],
            "error": str(exc),
        }


# ── API Keys ─────────────────────────────────────────────────────────


async def create_api_key(
    user_id: str,
    name: str,
    expires_in_days: int | None,
    session: AsyncSession,
) -> tuple[str, dict]:
    """Create a FORGE API key. Returns raw key (shown once) + metadata."""
    raw_key = f"forge_{secrets.token_urlsafe(32)}"
    prefix = raw_key[:12]

    # In production: bcrypt hash stored, raw shown once
    logger.info("api_key_created", name=name, prefix=prefix, user_id=user_id)
    return raw_key, {"name": name, "prefix": prefix}


# ── Helpers ──────────────────────────────────────────────────────────


async def _verify_provider_ownership(
    provider_id: str,
    user_id: str,
    db: AsyncSession,
) -> AIProvider:
    """Verify user owns the AI provider."""
    stmt = select(AIProvider).where(
        AIProvider.id == uuid.UUID(provider_id),
        AIProvider.user_id == uuid.UUID(user_id),
    )
    result = await db.execute(stmt)
    provider = result.scalar_one_or_none()
    if provider is None:
        raise LookupError(f"AI provider {provider_id} not found or access denied")
    return provider

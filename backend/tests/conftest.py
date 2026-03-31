"""
Shared test fixtures.

All tests use mocked/stubbed external services — never real APIs
(AGENTS.md rule #7).
"""

import os

import pytest
from httpx import ASGITransport, AsyncClient

# Set test env vars BEFORE importing app modules so pydantic-settings
# picks them up and we never touch real infrastructure.
os.environ.update(
    {
        "FORGE_ENV": "test",
        "FORGE_SECRET_KEY": "test-secret-key-not-for-production",
        "FORGE_ENCRYPTION_KEY": "MDEyMzQ1Njc4OWFiY2RlZjAxMjM0NTY3ODlhYmNkZWY=",  # 32 bytes b64
        "FORGE_HMAC_SECRET": "test-hmac-secret",
        "FORGE_FRONTEND_URL": "http://localhost:5173",
        "DATABASE_URL": "postgresql+asyncpg://test:test@localhost:5432/forge_test",
        "DATABASE_READ_URL": "postgresql+asyncpg://test:test@localhost:5432/forge_test",
        "NHOST_AUTH_URL": "https://auth.test.nhost.run",
        "NHOST_ADMIN_SECRET": "test-admin-secret",
        "REDIS_URL": "redis://localhost:6379/1",
        "SENTRY_DSN": "",
    }
)

from app.main import app  # noqa: E402 — must come after env setup


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def client():
    """Async HTTP client wired to the FORGE ASGI app."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

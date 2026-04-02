"""
Conftest for build agent tests — DOES NOT import app.main.

Sets env vars and provides fixtures for build agent testing.
Does not import the full ASGI app to avoid triggering heavy
module-level initialization (Redis connections, DB pools, etc.).
"""

import os

os.environ.update(
    {
        "FORGE_ENV": "test",
        "FORGE_SECRET_KEY": "test-secret-key-not-for-production",
        "FORGE_ENCRYPTION_KEY": "MDEyMzQ1Njc4OWFiY2RlZjAxMjM0NTY3ODlhYmNkZWY=",
        "FORGE_HMAC_SECRET": "test-hmac-secret",
        "FORGE_FRONTEND_URL": "http://localhost:5173",
        "DATABASE_URL": "postgresql+asyncpg://forge_dev:forge_dev_pass@localhost:5432/forge_dev",
        "DATABASE_READ_URL": "postgresql+asyncpg://forge_dev:forge_dev_pass@localhost:5432/forge_dev",
        "NHOST_AUTH_URL": "https://auth.test.nhost.run",
        "NHOST_ADMIN_SECRET": "test-admin-secret",
        "REDIS_URL": "redis://default:PASS@YOUR_UPSTASH_HOST:6379",
        "SENTRY_DSN": "",
        "CLOUDFLARE_ACCOUNT_ID": "YOUR_CLOUDFLARE_ACCOUNT_ID",
        "R2_ACCESS_KEY_ID": "c6feb61630533712c62a888194e1ff5b",
        "R2_SECRET_ACCESS_KEY": "2724e631732e4b036e774d07cf1f1d25078a85fc9e1c66485e3518fb99693f81",
        "R2_BUCKET_NAME": "forge-artifacts",
    }
)

import pytest  # noqa: E402


@pytest.fixture
def anyio_backend():
    return "asyncio"

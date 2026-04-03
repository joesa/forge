"""
Tests for the authentication API — all 7 endpoints.

All external services (Nhost Auth, Cloudflare Turnstile) are mocked.
Never call real external APIs in tests (AGENTS.md rule #7).
"""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.services.auth_service import NhostAuthError


# ── Fixtures ─────────────────────────────────────────────────────────

FAKE_USER_ID = str(uuid.uuid4())
FAKE_ACCESS_TOKEN = "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.fake"
FAKE_REFRESH_TOKEN = "fake-refresh-token-abc123"

NHOST_REGISTER_RESPONSE = {
    "session": {
        "accessToken": FAKE_ACCESS_TOKEN,
        "refreshToken": FAKE_REFRESH_TOKEN,
        "user": {
            "id": FAKE_USER_ID,
            "email": "new@forge.dev",
            "displayName": "New User",
            "avatarUrl": None,
            "createdAt": "2026-03-31T00:00:00Z",
        },
    },
}

NHOST_LOGIN_RESPONSE = {
    "session": {
        "accessToken": FAKE_ACCESS_TOKEN,
        "refreshToken": FAKE_REFRESH_TOKEN,
        "user": {
            "id": FAKE_USER_ID,
            "email": "user@forge.dev",
            "displayName": "Test User",
            "avatarUrl": None,
            "createdAt": "2026-03-31T00:00:00Z",
        },
    },
}

NHOST_REFRESH_RESPONSE = {
    "accessToken": "new-access-token",
    "refreshToken": "new-refresh-token",
}


def _make_fake_user():
    """Create a mock User ORM object for DB queries."""
    user = MagicMock()
    user.id = uuid.UUID(FAKE_USER_ID)
    user.email = "user@forge.dev"
    user.display_name = "Test User"
    user.avatar_url = None
    user.onboarded = False
    user.plan = "free"
    user.created_at = datetime(2026, 3, 31, tzinfo=timezone.utc)
    user.updated_at = datetime(2026, 3, 31, tzinfo=timezone.utc)
    return user


# ── POST /api/v1/auth/register ───────────────────────────────────────

@pytest.mark.anyio
async def test_register_success(client: AsyncClient):
    """Successful registration returns 201 with tokens + user."""
    with (
        patch(
            "app.api.v1.auth._verify_turnstile",
            new_callable=AsyncMock,
            return_value=True,
        ),
        patch(
            "app.api.v1.auth.register_user",
            new_callable=AsyncMock,
            return_value=NHOST_REGISTER_RESPONSE,
        ),
    ):
        resp = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "new@forge.dev",
                "password": "StrongPass123!",
                "display_name": "New User",
            },
            headers={"X-Turnstile-Token": "valid-token"},
        )

        assert resp.status_code == 201
        data = resp.json()
        assert data["access_token"] == FAKE_ACCESS_TOKEN
        assert data["refresh_token"] == FAKE_REFRESH_TOKEN
        assert data["user"]["email"] == "new@forge.dev"


@pytest.mark.anyio
async def test_register_missing_turnstile(client: AsyncClient):
    """Registration without Turnstile token returns 400."""
    resp = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "new@forge.dev",
            "password": "StrongPass123!",
            "display_name": "New User",
        },
    )
    assert resp.status_code == 400
    assert "Turnstile" in resp.json()["detail"]


@pytest.mark.anyio
async def test_register_invalid_email(client: AsyncClient):
    """Registration with invalid email returns 422 (validation error)."""
    resp = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "not-an-email",
            "password": "StrongPass123!",
            "display_name": "Bad Email User",
        },
        headers={"X-Turnstile-Token": "valid-token"},
    )
    assert resp.status_code == 422


@pytest.mark.anyio
async def test_register_short_password(client: AsyncClient):
    """Registration with password < 8 chars returns 422."""
    resp = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "new@forge.dev",
            "password": "short",
            "display_name": "Test",
        },
        headers={"X-Turnstile-Token": "valid-token"},
    )
    assert resp.status_code == 422


# ── POST /api/v1/auth/login ──────────────────────────────────────────

@pytest.mark.anyio
async def test_login_success(client: AsyncClient):
    """Successful login returns 200 with tokens + user."""
    with patch(
        "app.api.v1.auth.login_user",
        new_callable=AsyncMock,
        return_value=NHOST_LOGIN_RESPONSE,
    ):
        resp = await client.post(
            "/api/v1/auth/login",
            json={
                "email": "user@forge.dev",
                "password": "CorrectPass123!",
            },
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["access_token"] == FAKE_ACCESS_TOKEN
        assert data["refresh_token"] == FAKE_REFRESH_TOKEN
        assert data["user"]["email"] == "user@forge.dev"


@pytest.mark.anyio
async def test_login_wrong_password(client: AsyncClient):
    """Login with wrong password returns 401."""
    with patch(
        "app.api.v1.auth.login_user",
        new_callable=AsyncMock,
        side_effect=NhostAuthError(401, "Invalid credentials"),
    ):
        resp = await client.post(
            "/api/v1/auth/login",
            json={
                "email": "user@forge.dev",
                "password": "WrongPassword123!",
            },
        )

        assert resp.status_code == 401
        assert "Invalid credentials" in resp.json()["detail"]


@pytest.mark.anyio
async def test_login_invalid_email(client: AsyncClient):
    """Login with malformed email returns 422."""
    resp = await client.post(
        "/api/v1/auth/login",
        json={
            "email": "not-an-email",
            "password": "SomePass123!",
        },
    )
    assert resp.status_code == 422


# ── POST /api/v1/auth/logout ─────────────────────────────────────────

@pytest.mark.anyio
async def test_logout_success(client: AsyncClient):
    """Logout with valid token returns 200."""
    with patch(
        "app.api.v1.auth.logout_user",
        new_callable=AsyncMock,
    ):
        # We need the auth middleware to let us through — mock it
        with patch(
            "app.middleware.auth._fetch_jwks",
            new_callable=AsyncMock,
            return_value={"keys": []},
        ), patch(
            "app.middleware.auth.jwt.get_unverified_header",
            return_value={"kid": "test-kid", "alg": "RS256"},
        ), patch(
            "app.middleware.auth._find_rsa_key",
            return_value={"kty": "RSA", "kid": "test-kid", "n": "x", "e": "y", "use": "sig"},
        ), patch(
            "app.middleware.auth.jwt.decode",
            return_value={"sub": FAKE_USER_ID, "exp": 9999999999},
        ):
            resp = await client.post(
                "/api/v1/auth/logout",
                headers={"Authorization": f"Bearer {FAKE_ACCESS_TOKEN}"},
            )

            assert resp.status_code == 200
            assert resp.json()["message"] == "Logged out successfully"


@pytest.mark.anyio
async def test_logout_without_token(client: AsyncClient):
    """Logout without Authorization header returns 401."""
    resp = await client.post("/api/v1/auth/logout")
    assert resp.status_code == 401


# ── POST /api/v1/auth/refresh ────────────────────────────────────────

@pytest.mark.anyio
async def test_refresh_success(client: AsyncClient):
    """Token refresh returns new access + refresh tokens."""
    with patch(
        "app.api.v1.auth.refresh_tokens",
        new_callable=AsyncMock,
        return_value=NHOST_REFRESH_RESPONSE,
    ):
        resp = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": FAKE_REFRESH_TOKEN},
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["access_token"] == "new-access-token"
        assert data["refresh_token"] == "new-refresh-token"


@pytest.mark.anyio
async def test_refresh_invalid_token(client: AsyncClient):
    """Refresh with invalid token returns 401."""
    with patch(
        "app.api.v1.auth.refresh_tokens",
        new_callable=AsyncMock,
        side_effect=NhostAuthError(401, "Invalid refresh token"),
    ):
        resp = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": "expired-token"},
        )

        assert resp.status_code == 401
        assert "Invalid refresh token" in resp.json()["detail"]


# ── GET /api/v1/auth/me ──────────────────────────────────────────────

@pytest.mark.anyio
async def test_me_without_token(client: AsyncClient):
    """GET /me without auth returns 401."""
    resp = await client.get("/api/v1/auth/me")
    assert resp.status_code == 401


@pytest.mark.anyio
async def test_me_with_valid_token(client: AsyncClient):
    """GET /me with valid JWT returns user profile."""
    fake_user = _make_fake_user()

    with patch(
        "app.middleware.auth._fetch_jwks",
        new_callable=AsyncMock,
        return_value={"keys": []},
    ), patch(
        "app.middleware.auth.jwt.get_unverified_header",
        return_value={"kid": "test-kid", "alg": "RS256"},
    ), patch(
        "app.middleware.auth._find_rsa_key",
        return_value={"kty": "RSA", "kid": "test-kid", "n": "x", "e": "y", "use": "sig"},
    ), patch(
        "app.middleware.auth.jwt.decode",
        return_value={"sub": FAKE_USER_ID, "exp": 9999999999},
    ), patch(
        "app.api.v1.auth.get_current_user",
        new_callable=AsyncMock,
        return_value=fake_user,
    ):
        from app.main import app
        from app.core.database import get_read_session

        mock_session = AsyncMock()

        async def override_read_session():
            yield mock_session

        app.dependency_overrides[get_read_session] = override_read_session

        try:
            resp = await client.get(
                "/api/v1/auth/me",
                headers={"Authorization": f"Bearer {FAKE_ACCESS_TOKEN}"},
            )

            assert resp.status_code == 200
            data = resp.json()
            assert data["email"] == "user@forge.dev"
            assert data["display_name"] == "Test User"
            assert data["id"] == FAKE_USER_ID
        finally:
            app.dependency_overrides.pop(get_read_session, None)


# ── POST /api/v1/auth/forgot-password ────────────────────────────────

@pytest.mark.anyio
async def test_forgot_password_success(client: AsyncClient):
    """Forgot password always returns success (no email enumeration)."""
    with patch(
        "app.api.v1.auth.forgot_password",
        new_callable=AsyncMock,
    ):
        resp = await client.post(
            "/api/v1/auth/forgot-password",
            json={"email": "user@forge.dev"},
        )

        assert resp.status_code == 200
        assert "reset link" in resp.json()["message"].lower()


@pytest.mark.anyio
async def test_forgot_password_invalid_email(client: AsyncClient):
    """Forgot password with malformed email returns 422."""
    resp = await client.post(
        "/api/v1/auth/forgot-password",
        json={"email": "not-an-email"},
    )
    assert resp.status_code == 422


# ── POST /api/v1/auth/reset-password ─────────────────────────────────

@pytest.mark.anyio
async def test_reset_password_success(client: AsyncClient):
    """Reset password with valid token returns success."""
    with patch(
        "app.api.v1.auth.reset_password",
        new_callable=AsyncMock,
    ):
        resp = await client.post(
            "/api/v1/auth/reset-password",
            json={
                "token": "valid-reset-token",
                "new_password": "NewStrongPass123!",
            },
        )

        assert resp.status_code == 200
        assert "reset successfully" in resp.json()["message"].lower()


@pytest.mark.anyio
async def test_reset_password_invalid_token(client: AsyncClient):
    """Reset password with invalid/expired token returns 400."""
    with patch(
        "app.api.v1.auth.reset_password",
        new_callable=AsyncMock,
        side_effect=NhostAuthError(400, "Invalid or expired token"),
    ):
        resp = await client.post(
            "/api/v1/auth/reset-password",
            json={
                "token": "expired-token",
                "new_password": "NewStrongPass123!",
            },
        )

        assert resp.status_code == 400
        assert "Invalid or expired token" in resp.json()["detail"]


@pytest.mark.anyio
async def test_reset_password_short_password(client: AsyncClient):
    """Reset password with short new password returns 422."""
    resp = await client.post(
        "/api/v1/auth/reset-password",
        json={
            "token": "valid-token",
            "new_password": "short",
        },
    )
    assert resp.status_code == 422

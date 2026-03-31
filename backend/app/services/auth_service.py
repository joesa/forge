"""
Auth service — wraps Nhost Auth REST API.

All external HTTP calls to Nhost live here so route handlers
stay thin and testable. Never call real external APIs in tests
(AGENTS.md rule #7); mock this service instead.
"""

import uuid

import httpx
import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.user import User

logger = structlog.get_logger(__name__)

_NHOST_TIMEOUT = 15  # seconds


class NhostAuthError(Exception):
    """Raised when Nhost Auth returns a non-2xx response."""

    def __init__(self, status_code: int, detail: str) -> None:
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)


# ── Helpers ──────────────────────────────────────────────────────────

def _nhost_url(path: str) -> str:
    """Build full Nhost Auth URL from the configured base."""
    base = settings.NHOST_AUTH_URL.rstrip("/")
    return f"{base}{path}"


def _admin_headers() -> dict[str, str]:
    """Headers for Nhost admin-level requests."""
    return {
        "Content-Type": "application/json",
        "x-hasura-admin-secret": settings.NHOST_ADMIN_SECRET,
    }


# ── Public API ───────────────────────────────────────────────────────

async def register_user(
    email: str,
    password: str,
    display_name: str,
) -> dict:
    """
    Register a new user via Nhost Auth.

    Returns the Nhost response dict containing session + user data.

    Raises
    ------
    NhostAuthError
        If Nhost rejects the registration (duplicate email, weak
        password, etc.).
    """
    payload = {
        "email": email,
        "password": password,
        "options": {
            "displayName": display_name,
        },
    }

    async with httpx.AsyncClient(timeout=_NHOST_TIMEOUT) as client:
        resp = await client.post(
            _nhost_url("/v1/signup/email-password"),
            json=payload,
            headers=_admin_headers(),
        )

    if resp.status_code >= 400:
        body = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
        detail = body.get("message", resp.text)
        logger.warning(
            "nhost_register_failed",
            status=resp.status_code,
            detail=detail,
        )
        raise NhostAuthError(resp.status_code, detail)

    return resp.json()


async def login_user(email: str, password: str) -> dict:
    """
    Authenticate via Nhost Auth and return session data.

    Returns dict with keys: session.accessToken, session.refreshToken, etc.

    Raises
    ------
    NhostAuthError
        On invalid credentials or other Nhost errors.
    """
    payload = {"email": email, "password": password}

    async with httpx.AsyncClient(timeout=_NHOST_TIMEOUT) as client:
        resp = await client.post(
            _nhost_url("/v1/signin/email-password"),
            json=payload,
            headers={"Content-Type": "application/json"},
        )

    if resp.status_code >= 400:
        body = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
        detail = body.get("message", resp.text)
        logger.warning(
            "nhost_login_failed",
            status=resp.status_code,
            detail=detail,
        )
        raise NhostAuthError(resp.status_code, detail)

    return resp.json()


async def refresh_tokens(refresh_token: str) -> dict:
    """
    Exchange a refresh token for new access + refresh tokens.

    Returns dict with ``accessToken`` and ``refreshToken``.

    Raises
    ------
    NhostAuthError
        If the refresh token is invalid or expired.
    """
    payload = {"refreshToken": refresh_token}

    async with httpx.AsyncClient(timeout=_NHOST_TIMEOUT) as client:
        resp = await client.post(
            _nhost_url("/v1/token"),
            json=payload,
            headers={"Content-Type": "application/json"},
        )

    if resp.status_code >= 400:
        body = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
        detail = body.get("message", resp.text)
        logger.warning(
            "nhost_refresh_failed",
            status=resp.status_code,
            detail=detail,
        )
        raise NhostAuthError(resp.status_code, detail)

    return resp.json()


async def get_current_user(
    user_id: uuid.UUID,
    session: AsyncSession,
) -> User | None:
    """
    Fetch user from **our** database by ID.

    Uses a read session (caller must supply a replica-bound session).
    """
    stmt = select(User).where(User.id == user_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def logout_user(access_token: str) -> None:
    """
    Sign out via Nhost Auth (invalidates the refresh token family).

    Raises
    ------
    NhostAuthError
        If Nhost rejects the signout request.
    """
    async with httpx.AsyncClient(timeout=_NHOST_TIMEOUT) as client:
        resp = await client.post(
            _nhost_url("/v1/signout"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {access_token}",
            },
            json={},
        )

    if resp.status_code >= 400:
        body = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
        detail = body.get("message", resp.text)
        logger.warning(
            "nhost_logout_failed",
            status=resp.status_code,
            detail=detail,
        )
        raise NhostAuthError(resp.status_code, detail)


async def forgot_password(email: str) -> None:
    """
    Trigger Nhost password-reset email.

    Always returns None to avoid leaking whether an email exists.

    Raises
    ------
    NhostAuthError
        On unexpected Nhost errors (not user-facing).
    """
    payload = {"email": email}

    async with httpx.AsyncClient(timeout=_NHOST_TIMEOUT) as client:
        resp = await client.post(
            _nhost_url("/v1/user/password/reset"),
            json=payload,
            headers={"Content-Type": "application/json"},
        )

    # We intentionally swallow 4xx here to avoid email enumeration.
    # Only log server errors.
    if resp.status_code >= 500:
        logger.error(
            "nhost_forgot_password_error",
            status=resp.status_code,
        )
        raise NhostAuthError(resp.status_code, "Password reset service error")


async def reset_password(token: str, new_password: str) -> None:
    """
    Complete the password reset flow with the emailed token.

    Raises
    ------
    NhostAuthError
        If the token is invalid/expired or new password doesn't meet
        Nhost requirements.
    """
    payload = {"ticket": token, "newPassword": new_password}

    async with httpx.AsyncClient(timeout=_NHOST_TIMEOUT) as client:
        resp = await client.post(
            _nhost_url("/v1/user/password"),
            json=payload,
            headers={"Content-Type": "application/json"},
        )

    if resp.status_code >= 400:
        body = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
        detail = body.get("message", resp.text)
        logger.warning(
            "nhost_reset_password_failed",
            status=resp.status_code,
            detail=detail,
        )
        raise NhostAuthError(resp.status_code, detail)

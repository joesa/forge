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
from app.core.database import get_write_session
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
    base = settings.NHOST_AUTH_URL.rstrip("/")
    return f"{base}{path}"


def _admin_headers() -> dict[str, str]:
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
    Register a new user via Nhost Auth, then persist a user record
    in the Northflank PostgreSQL database.

    Step 1: Create auth identity in Nhost (handles password hashing,
            email verification, JWT issuance).
    Step 2: Create User row in our database using Nhost's user ID
            as the primary key so the two systems stay in sync.

    Raises
    ------
    NhostAuthError
        If Nhost rejects the registration (duplicate email, etc.).
    """
    payload = {
        "email": email,
        "password": password,
        "options": {
            "displayName": display_name,
        },
    }

    # Step 1 — create auth identity in Nhost
    async with httpx.AsyncClient(timeout=_NHOST_TIMEOUT) as client:
        resp = await client.post(
            _nhost_url("/signup/email-password"),
            json=payload,
            headers=_admin_headers(),
        )

    if resp.status_code >= 400:
        body = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
        detail = body.get("message", resp.text)
        logger.warning("nhost_register_failed", status=resp.status_code, detail=detail)
        raise NhostAuthError(resp.status_code, detail)

    nhost_data = resp.json()

    # Step 2 — persist user in Northflank PostgreSQL
    # Use the Nhost user ID as our primary key so the two systems
    # are permanently linked. If this write fails, the user exists
    # in Nhost but not in our DB — that's caught on next login via
    # get_or_create_user_on_login().
    nhost_user = nhost_data.get("user", {})
    nhost_user_id = nhost_user.get("id")

    if nhost_user_id:
        async with get_write_session() as db:
            # Guard against duplicate inserts (e.g. retry after network error)
            existing = await db.get(User, uuid.UUID(nhost_user_id))
            if not existing:
                user = User(
                    id=uuid.UUID(nhost_user_id),
                    email=email,
                    display_name=display_name,
                    onboarded=False,
                    plan="free",
                )
                db.add(user)
                await db.commit()
                logger.info(
                    "user_created_in_db",
                    user_id=str(nhost_user_id),
                    email=email,
                )
    else:
        # Nhost didn't return a user ID — log but don't fail registration.
        # The user record will be created on first successful login
        # via get_or_create_user_on_login().
        logger.warning(
            "nhost_register_no_user_id",
            email=email,
            response_keys=list(nhost_data.keys()),
        )

    return nhost_data


async def get_or_create_user_on_login(
    nhost_user_id: str,
    email: str,
    display_name: str,
) -> User:
    """
    Called after successful Nhost login to ensure the user row
    exists in our database.

    This is the safety net for users who registered before the
    DB write was in place, or when the write failed during registration.
    Uses get_write_session() because it may INSERT.
    """
    async with get_write_session() as db:
        user_uuid = uuid.UUID(nhost_user_id)
        user = await db.get(User, user_uuid)

        if user is None:
            user = User(
                id=user_uuid,
                email=email,
                display_name=display_name or email.split("@")[0],
                onboarded=False,
                plan="free",
            )
            db.add(user)
            await db.commit()
            await db.refresh(user)
            logger.info(
                "user_created_on_login",
                user_id=nhost_user_id,
                email=email,
            )

        return user


async def login_user(email: str, password: str) -> dict:
    """
    Authenticate via Nhost Auth, then ensure the user row exists
    in our Northflank PostgreSQL database.

    Returns dict with session tokens plus our User record.
    """
    payload = {"email": email, "password": password}

    async with httpx.AsyncClient(timeout=_NHOST_TIMEOUT) as client:
        resp = await client.post(
            _nhost_url("/signin/email-password"),
            json=payload,
            headers={"Content-Type": "application/json"},
        )

    if resp.status_code >= 400:
        body = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
        detail = body.get("message", resp.text)
        logger.warning("nhost_login_failed", status=resp.status_code, detail=detail)
        raise NhostAuthError(resp.status_code, detail)

    nhost_data = resp.json()

    # Ensure user row exists in our DB (safety net for edge cases)
    nhost_user = nhost_data.get("user", {})
    if nhost_user.get("id"):
        await get_or_create_user_on_login(
            nhost_user_id=nhost_user["id"],
            email=nhost_user.get("email", email),
            display_name=nhost_user.get("displayName", ""),
        )

    return nhost_data


async def refresh_tokens(refresh_token: str) -> dict:
    """Exchange a refresh token for new access + refresh tokens."""
    payload = {"refreshToken": refresh_token}

    async with httpx.AsyncClient(timeout=_NHOST_TIMEOUT) as client:
        resp = await client.post(
            _nhost_url("/token"),
            json=payload,
            headers={"Content-Type": "application/json"},
        )

    if resp.status_code >= 400:
        body = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
        detail = body.get("message", resp.text)
        logger.warning("nhost_refresh_failed", status=resp.status_code, detail=detail)
        raise NhostAuthError(resp.status_code, detail)

    return resp.json()


async def get_current_user(
    user_id: uuid.UUID,
    session: AsyncSession,
) -> User | None:
    """
    Fetch user from Northflank PostgreSQL by ID.

    Caller must supply a read-replica-bound session (get_read_session).
    """
    stmt = select(User).where(User.id == user_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def logout_user(access_token: str) -> None:
    """Sign out via Nhost Auth (invalidates the refresh token family)."""
    async with httpx.AsyncClient(timeout=_NHOST_TIMEOUT) as client:
        resp = await client.post(
            _nhost_url("/signout"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {access_token}",
            },
            json={},
        )

    if resp.status_code >= 400:
        body = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
        detail = body.get("message", resp.text)
        logger.warning("nhost_logout_failed", status=resp.status_code, detail=detail)
        raise NhostAuthError(resp.status_code, detail)


async def forgot_password(email: str) -> None:
    """
    Trigger Nhost password-reset email.
    Swallows 4xx to avoid email enumeration.
    """
    async with httpx.AsyncClient(timeout=_NHOST_TIMEOUT) as client:
        resp = await client.post(
            _nhost_url("/user/password/reset"),
            json={"email": email},
            headers={"Content-Type": "application/json"},
        )

    if resp.status_code >= 500:
        logger.error("nhost_forgot_password_error", status=resp.status_code)
        raise NhostAuthError(resp.status_code, "Password reset service error")


async def reset_password(token: str, new_password: str) -> None:
    """Complete the password reset flow with the emailed token."""
    payload = {"ticket": token, "newPassword": new_password}

    async with httpx.AsyncClient(timeout=_NHOST_TIMEOUT) as client:
        resp = await client.post(
            _nhost_url("/user/password"),
            json=payload,
            headers={"Content-Type": "application/json"},
        )

    if resp.status_code >= 400:
        body = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
        detail = body.get("message", resp.text)
        logger.warning("nhost_reset_password_failed", status=resp.status_code, detail=detail)
        raise NhostAuthError(resp.status_code, detail)
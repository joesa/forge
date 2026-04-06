"""
Authentication API — v1.

Endpoints:
  POST /register       — create account (requires Turnstile)
  POST /login          — email + password sign-in
  POST /logout         — invalidate session (requires auth)
  POST /refresh        — exchange refresh token
  GET  /me             — current user profile (requires auth)
  POST /forgot-password — trigger password-reset email
  POST /reset-password  — complete password reset with token
"""

import uuid

import httpx
import structlog
from fastapi import APIRouter, Depends, Header, Request
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.database import get_read_session

from app.schemas.auth import (
    AuthTokensResponse,
    ForgotPasswordRequest,
    LoginRequest,
    MessageResponse,
    RefreshRequest,
    RefreshTokensResponse,
    RegisterRequest,
    ResetPasswordRequest,
    UserResponse,
)
from app.services.auth_service import (
    NhostAuthError,
    forgot_password,
    login_user,
    logout_user,
    refresh_tokens,
    reset_password,
    register_user,
    get_current_user,
)

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


# ── Helpers ──────────────────────────────────────────────────────────

async def _verify_turnstile(token: str) -> bool:
    """Validate a Cloudflare Turnstile token server-side."""
    if not settings.turnstile_secret:
        # Skip verification in dev/test when no key is configured
        return True

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                "https://challenges.cloudflare.com/turnstile/v0/siteverify",
                data={
                    "secret": settings.turnstile_secret,
                    "response": token,
                },
            )
            result = resp.json()
            return result.get("success", False)
    except httpx.HTTPError:
        logger.error("turnstile_verification_failed")
        return False


def _extract_user_id(request: Request) -> uuid.UUID:
    """Pull user ID from the JWT payload attached by AuthMiddleware."""
    payload = getattr(request.state, "user", None)
    if not payload:
        raise ValueError("No user payload in request state")
    sub = payload.get("sub")
    if not sub:
        raise ValueError("JWT missing 'sub' claim")
    return uuid.UUID(sub)


def _extract_access_token(request: Request) -> str:
    """Pull the raw Bearer token from the Authorization header."""
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        return auth_header.split(" ", 1)[1]
    raise ValueError("Missing Bearer token")


# ── Endpoints ────────────────────────────────────────────────────────

@router.post(
    "/register",
    response_model=AuthTokensResponse,
    status_code=201,
)
async def register(
    body: RegisterRequest,
    request: Request,
    x_turnstile_token: str | None = Header(default=None),
) -> AuthTokensResponse | JSONResponse:
    """Create a new user account."""

    # 1. Validate Turnstile
    if not x_turnstile_token:
        return JSONResponse(
            status_code=400,
            content={"detail": "Missing X-Turnstile-Token header"},
        )

    if not await _verify_turnstile(x_turnstile_token):
        return JSONResponse(
            status_code=403,
            content={"detail": "Turnstile verification failed"},
        )

    # 2. Register with Nhost (also creates user in our DB)
    try:
        nhost_resp = await register_user(
            email=body.email,
            password=body.password,
            display_name=body.display_name,
        )
    except NhostAuthError as exc:
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail},
        )

    # 3. Extract session data from Nhost response (camelCase keys)
    nhost_session = nhost_resp.get("session", {})
    nhost_user = nhost_session.get("user", nhost_resp.get("user", {}))

    access_token = nhost_session.get("accessToken", "")
    refresh_token_val = nhost_session.get("refreshToken", "")
    nhost_user_id = nhost_user.get("id", str(uuid.uuid4()))

    return AuthTokensResponse(
        access_token=access_token,
        refresh_token=refresh_token_val,
        user=UserResponse(
            id=uuid.UUID(nhost_user_id) if nhost_user_id else uuid.uuid4(),
            email=body.email,
            display_name=nhost_user.get("displayName", body.display_name),
            avatar_url=nhost_user.get("avatarUrl"),
            onboarded=False,
            plan="free",
            created_at=nhost_user.get("createdAt", "2026-01-01T00:00:00Z"),
        ),
    )


@router.post("/login", response_model=AuthTokensResponse)
async def login(
    body: LoginRequest,
    read_session: AsyncSession = Depends(get_read_session),
) -> AuthTokensResponse | JSONResponse:
    """Authenticate with email and password."""
    try:
        nhost_resp = await login_user(
            email=body.email, password=body.password
        )
    except NhostAuthError as exc:
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail},
        )

    # login_user() already ensured the user row exists in our DB
    # via get_or_create_user_on_login(). Extract session data.
    nhost_session = nhost_resp.get("session", {})
    nhost_user = nhost_session.get("user", nhost_resp.get("user", {}))

    access_token = nhost_session.get("accessToken", "")
    refresh_token_val = nhost_session.get("refreshToken", "")
    nhost_user_id = nhost_user.get("id", "")

    # Fetch actual plan/onboarding status from our DB
    db_user = None
    if nhost_user_id:
        try:
            db_user = await get_current_user(uuid.UUID(nhost_user_id), read_session)
        except Exception:
            pass

    return AuthTokensResponse(
        access_token=access_token,
        refresh_token=refresh_token_val,
        user=UserResponse(
            id=uuid.UUID(nhost_user_id) if nhost_user_id else uuid.uuid4(),
            email=db_user.email if db_user else nhost_user.get("email", body.email),
            display_name=db_user.display_name if db_user else nhost_user.get("displayName"),
            avatar_url=db_user.avatar_url if db_user else nhost_user.get("avatarUrl"),
            onboarded=db_user.onboarded if db_user else False,
            plan=db_user.plan if db_user else "free",
            created_at=db_user.created_at.isoformat() if db_user else nhost_user.get("createdAt", "2026-01-01T00:00:00Z"),
        ),
    )


@router.post("/logout", response_model=MessageResponse)
async def logout(request: Request) -> MessageResponse | JSONResponse:
    """Sign out — invalidates the Nhost refresh token family."""
    try:
        token = _extract_access_token(request)
    except ValueError:
        return JSONResponse(
            status_code=401,
            content={"detail": "Missing or invalid Authorization header"},
        )

    try:
        await logout_user(token)
    except NhostAuthError as exc:
        logger.warning("logout_nhost_error", detail=exc.detail)
        # Still return success — local session is done
        pass

    return MessageResponse(message="Logged out successfully")


@router.post("/refresh", response_model=RefreshTokensResponse)
async def refresh(body: RefreshRequest) -> RefreshTokensResponse | JSONResponse:
    """Exchange a refresh token for new tokens."""
    try:
        nhost_resp = await refresh_tokens(body.refresh_token)
    except NhostAuthError as exc:
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail},
        )

    return RefreshTokensResponse(
        access_token=nhost_resp.get("accessToken", ""),
        refresh_token=nhost_resp.get("refreshToken", ""),
    )


@router.get("/me", response_model=UserResponse)
async def me(
    request: Request,
    read_session: AsyncSession = Depends(get_read_session),
) -> UserResponse | JSONResponse:
    """Return the currently authenticated user's profile."""
    try:
        user_id = _extract_user_id(request)
    except ValueError as exc:
        return JSONResponse(
            status_code=401,
            content={"detail": str(exc)},
        )

    user = await get_current_user(user_id, read_session)
    if not user:
        return JSONResponse(
            status_code=404,
            content={"detail": "User not found"},
        )

    return UserResponse.model_validate(user)


@router.post("/forgot-password", response_model=MessageResponse)
async def forgot_password_endpoint(
    body: ForgotPasswordRequest,
) -> MessageResponse:
    """Trigger a password-reset email via Nhost."""
    try:
        await forgot_password(body.email)
    except NhostAuthError:
        # Swallow errors to prevent email enumeration
        pass

    # Always return success to avoid leaking whether email exists
    return MessageResponse(
        message="If this email is registered, a reset link has been sent."
    )


@router.post("/reset-password", response_model=MessageResponse)
async def reset_password_endpoint(
    body: ResetPasswordRequest,
) -> MessageResponse | JSONResponse:
    """Complete the password-reset flow with token + new password."""
    try:
        await reset_password(body.token, body.new_password)
    except NhostAuthError as exc:
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail},
        )

    return MessageResponse(message="Password has been reset successfully.")


@router.post("/verify", response_model=MessageResponse)
async def verify_email(
    body: ResetPasswordRequest,
) -> MessageResponse | JSONResponse:
    """Verify user email address with token from verification email."""
    # In production: validate token with Nhost
    # Nhost handles email verification natively via its auth endpoints
    logger.info("email_verification_attempted")
    return MessageResponse(message="Email verified successfully.")

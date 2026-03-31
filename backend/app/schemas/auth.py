"""
Pydantic v2 schemas for authentication endpoints.

All request/response bodies live here — never raw dicts in routes.
"""

import datetime
import uuid

from pydantic import BaseModel, EmailStr, Field


# ── Request schemas ──────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    """POST /api/v1/auth/register body."""

    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    display_name: str = Field(min_length=1, max_length=128)


class LoginRequest(BaseModel):
    """POST /api/v1/auth/login body."""

    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class RefreshRequest(BaseModel):
    """POST /api/v1/auth/refresh body."""

    refresh_token: str = Field(min_length=1)


class ForgotPasswordRequest(BaseModel):
    """POST /api/v1/auth/forgot-password body."""

    email: EmailStr


class ResetPasswordRequest(BaseModel):
    """POST /api/v1/auth/reset-password body."""

    token: str = Field(min_length=1)
    new_password: str = Field(min_length=8, max_length=128)


# ── Response schemas ─────────────────────────────────────────────────

class UserResponse(BaseModel):
    """Public-facing user representation."""

    id: uuid.UUID
    email: str
    display_name: str | None = None
    avatar_url: str | None = None
    onboarded: bool = False
    plan: str = "free"
    created_at: datetime.datetime

    model_config = {"from_attributes": True}


class AuthTokensResponse(BaseModel):
    """Token pair returned on login / register / refresh."""

    access_token: str
    refresh_token: str
    user: UserResponse


class RefreshTokensResponse(BaseModel):
    """Response for token refresh — no user payload needed."""

    access_token: str
    refresh_token: str


class MessageResponse(BaseModel):
    """Generic success message."""

    message: str

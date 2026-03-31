"""
Nhost JWT authentication middleware.

• Fetches JWKS from ``NHOST_AUTH_URL/v1/.well-known/jwks.json``
• Caches the key-set in Redis for 1 hour
• Validates signature, expiry, and issuer
• Attaches decoded token payload to ``request.state.user``
• Skips public routes: /health, /api/v1/auth/login, /api/v1/auth/register
"""

import json
import time
from typing import Any

import httpx
import structlog
from jose import JWTError, jwt
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.config import settings
from app.core.redis import get_cache, set_cache

logger = structlog.get_logger(__name__)

# Routes that do NOT require authentication
PUBLIC_PATHS: set[str] = {
    "/health",
    "/docs",
    "/openapi.json",
    "/redoc",
    "/api/v1/auth/login",
    "/api/v1/auth/register",
}

_JWKS_CACHE_KEY = "forge:jwks"
_JWKS_TTL = 3600  # 1 hour


async def _fetch_jwks() -> dict[str, Any]:
    """Fetch JWKS from Nhost, caching in Redis for 1 h."""
    cached = await get_cache(_JWKS_CACHE_KEY)
    if cached:
        return json.loads(cached)

    url = f"{settings.NHOST_AUTH_URL}/v1/.well-known/jwks.json"
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        jwks = resp.json()

    await set_cache(_JWKS_CACHE_KEY, json.dumps(jwks), _JWKS_TTL)
    return jwks


def _find_rsa_key(jwks: dict[str, Any], kid: str) -> dict[str, str] | None:
    """Locate the JWK matching the token's key-id."""
    for key in jwks.get("keys", []):
        if key.get("kid") == kid:
            return {
                "kty": key["kty"],
                "kid": key["kid"],
                "use": key.get("use", "sig"),
                "n": key["n"],
                "e": key["e"],
            }
    return None


class AuthMiddleware(BaseHTTPMiddleware):
    """Validate Nhost JWTs on non-public routes."""

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        # Skip public endpoints
        if request.url.path in PUBLIC_PATHS:
            return await call_next(request)

        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return JSONResponse(
                status_code=401,
                content={"detail": "Missing or invalid Authorization header"},
            )

        token = auth_header.split(" ", 1)[1]

        try:
            # Decode header to get key id
            unverified_header = jwt.get_unverified_header(token)
            kid = unverified_header.get("kid")
            if not kid:
                raise JWTError("Token header missing 'kid'")

            jwks = await _fetch_jwks()
            rsa_key = _find_rsa_key(jwks, kid)
            if rsa_key is None:
                raise JWTError(f"No matching JWK for kid={kid}")

            payload = jwt.decode(
                token,
                rsa_key,
                algorithms=["RS256"],
                issuer=settings.NHOST_AUTH_URL,
                options={"verify_aud": False},
            )

            # Reject expired tokens explicitly (jose also checks, belt-and-suspenders)
            if payload.get("exp", 0) < time.time():
                raise JWTError("Token has expired")

            request.state.user = payload

        except JWTError as exc:
            logger.warning("jwt_validation_failed", error=str(exc))
            return JSONResponse(
                status_code=401,
                content={"detail": "Invalid or expired token"},
            )
        except httpx.HTTPError as exc:
            logger.error("jwks_fetch_failed", error=str(exc))
            return JSONResponse(
                status_code=503,
                content={"detail": "Authentication service unavailable"},
            )
        except Exception as exc:
            logger.error("auth_unexpected_error", error=str(exc))
            return JSONResponse(
                status_code=500,
                content={"detail": "Internal authentication error"},
            )

        return await call_next(request)

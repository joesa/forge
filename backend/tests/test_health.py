"""
Tests for GET /health and middleware behaviour.
"""

import pytest


@pytest.mark.asyncio
async def test_health_returns_200(client):
    """GET /health must return 200 with {"status": "ok"}."""
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_health_has_request_id_header(client):
    """Every response must carry an X-Request-ID header."""
    resp = await client.get("/health")
    assert "x-request-id" in resp.headers
    # Must be a UUID4
    request_id = resp.headers["x-request-id"]
    assert len(request_id) == 36  # UUID4 format: 8-4-4-4-12


@pytest.mark.asyncio
async def test_health_propagates_client_request_id(client):
    """If client sends X-Request-ID, server echoes it back."""
    custom_id = "my-custom-request-id-123"
    resp = await client.get("/health", headers={"X-Request-ID": custom_id})
    assert resp.headers["x-request-id"] == custom_id


@pytest.mark.asyncio
async def test_cors_allows_configured_origin(client):
    """CORS preflight should accept the configured frontend origin."""
    resp = await client.options(
        "/health",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert resp.headers.get("access-control-allow-origin") == "http://localhost:5173"


@pytest.mark.asyncio
async def test_cors_rejects_unknown_origin(client):
    """CORS should NOT return allow-origin for an unknown domain."""
    resp = await client.options(
        "/health",
        headers={
            "Origin": "https://evil.example.com",
            "Access-Control-Request-Method": "GET",
        },
    )
    # FastAPI CORSMiddleware simply omits the header for disallowed origins
    assert resp.headers.get("access-control-allow-origin") != "https://evil.example.com"


@pytest.mark.asyncio
async def test_protected_route_returns_401_without_token(client):
    """A non-public route must reject requests with no Authorization header."""
    resp = await client.get("/api/v1/projects")
    # /api/v1/projects is NOT in the public paths, so auth middleware blocks it
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Missing or invalid Authorization header"

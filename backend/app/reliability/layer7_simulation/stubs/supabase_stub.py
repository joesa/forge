"""
Supabase API stubs for Wiremock simulation.

Covers:
  - GET    /rest/v1/{table}    → returns mock data array (5 records)
  - POST   /rest/v1/{table}    → returns created record
  - PATCH  /rest/v1/{table}    → returns updated record
  - DELETE /rest/v1/{table}    → returns 204
  - POST   /auth/v1/signup     → returns user + session
  - POST   /auth/v1/token      → returns access + refresh tokens
"""

from __future__ import annotations

from app.reliability.layer7_simulation.stub_registry import StubConfig, StubMapping


def _supabase_stubs() -> list[StubMapping]:
    """Return all Supabase-related Wiremock stub mappings."""
    mock_records = [
        {"id": f"rec-{i}", "name": f"Record {i}", "created_at": "2026-01-01T00:00:00Z"}
        for i in range(1, 6)
    ]

    return [
        # ── GET /rest/v1/{table} ────────────────────────────────────
        StubMapping(
            name="supabase_select",
            request={
                "method": "GET",
                "urlPathPattern": "/rest/v1/[a-zA-Z_]+",
            },
            response={
                "status": 200,
                "headers": {
                    "Content-Type": "application/json",
                    "Content-Profile": "public",
                },
                "jsonBody": mock_records,
            },
            priority=5,
        ),
        # ── POST /rest/v1/{table} ───────────────────────────────────
        StubMapping(
            name="supabase_insert",
            request={
                "method": "POST",
                "urlPathPattern": "/rest/v1/[a-zA-Z_]+",
            },
            response={
                "status": 201,
                "headers": {
                    "Content-Type": "application/json",
                    "Content-Profile": "public",
                },
                "jsonBody": {
                    "id": "rec-new-1",
                    "name": "New Record",
                    "created_at": "2026-01-01T00:00:00Z",
                },
            },
            priority=5,
        ),
        # ── PATCH /rest/v1/{table} ──────────────────────────────────
        StubMapping(
            name="supabase_update",
            request={
                "method": "PATCH",
                "urlPathPattern": "/rest/v1/[a-zA-Z_]+",
            },
            response={
                "status": 200,
                "headers": {
                    "Content-Type": "application/json",
                    "Content-Profile": "public",
                },
                "jsonBody": {
                    "id": "rec-1",
                    "name": "Updated Record",
                    "updated_at": "2026-01-02T00:00:00Z",
                },
            },
            priority=5,
        ),
        # ── DELETE /rest/v1/{table} ─────────────────────────────────
        StubMapping(
            name="supabase_delete",
            request={
                "method": "DELETE",
                "urlPathPattern": "/rest/v1/[a-zA-Z_]+",
            },
            response={
                "status": 204,
                "headers": {},
            },
            priority=5,
        ),
        # ── POST /auth/v1/signup ────────────────────────────────────
        StubMapping(
            name="supabase_signup",
            request={
                "method": "POST",
                "urlPathPattern": "/auth/v1/signup",
            },
            response={
                "status": 200,
                "headers": {"Content-Type": "application/json"},
                "jsonBody": {
                    "user": {
                        "id": "a1b2c3d4-e5f6-7a8b-9c0d-1e2f3a4b5c6d",
                        "email": "test@example.com",
                        "aud": "authenticated",
                        "role": "authenticated",
                        "created_at": "2026-01-01T00:00:00Z",
                    },
                    "session": {
                        "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJhMWIyYzNkNCJ9.dGVzdF90b2tlbg",
                        "refresh_token": "v1.MHhkZWFkYmVlZjAxMjM0NTY3ODlhYmNkZWYwMTIzNDU",
                        "token_type": "bearer",
                        "expires_in": 3600,
                    },
                },
            },
            priority=1,
        ),
        # ── POST /auth/v1/token ─────────────────────────────────────
        StubMapping(
            name="supabase_token",
            request={
                "method": "POST",
                "urlPathPattern": "/auth/v1/token",
            },
            response={
                "status": 200,
                "headers": {"Content-Type": "application/json"},
                "jsonBody": {
                    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJhMWIyYzNkNCJ9.dGVzdF90b2tlbg",
                    "refresh_token": "v1.MHhkZWFkYmVlZjAxMjM0NTY3ODlhYmNkZWYwMTIzNDU",
                    "token_type": "bearer",
                    "expires_in": 3600,
                    "user": {
                        "id": "a1b2c3d4-e5f6-7a8b-9c0d-1e2f3a4b5c6d",
                        "email": "test@example.com",
                    },
                },
            },
            priority=1,
        ),
    ]


supabase_stub = StubConfig(
    service_name="supabase",
    base_url_pattern="/rest/v1|/auth/v1",
    description="Supabase REST + Auth stubs (CRUD, signup, token refresh)",
    mappings=_supabase_stubs(),
)

"""
Resend email API stubs for Wiremock simulation.

Covers:
  - POST /emails → returns email ID confirmation
"""

from __future__ import annotations

from app.reliability.layer7_simulation.stub_registry import StubConfig, StubMapping


def _resend_stubs() -> list[StubMapping]:
    """Return all Resend-related Wiremock stub mappings."""
    return [
        StubMapping(
            name="resend_send_email",
            request={
                "method": "POST",
                "urlPathPattern": "/emails",
            },
            response={
                "status": 200,
                "headers": {"Content-Type": "application/json"},
                "jsonBody": {
                    "id": "e7a1b2c3-d4e5-6f7a-8b9c-0d1e2f3a4b5c",
                    "from": "onboarding@resend.dev",
                    "to": "test@example.com",
                    "created_at": "2026-01-01T00:00:00.000Z",
                },
            },
            priority=1,
        ),
    ]


resend_stub = StubConfig(
    service_name="resend",
    base_url_pattern="/emails",
    description="Resend email API stubs (send email)",
    mappings=_resend_stubs(),
)

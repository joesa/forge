"""
Twilio API stubs for Wiremock simulation.

Covers:
  - POST /2010-04-01/Accounts/{sid}/Messages.json → SMS send
"""

from __future__ import annotations

from app.reliability.layer7_simulation.stub_registry import StubConfig, StubMapping


def _twilio_stubs() -> list[StubMapping]:
    """Return all Twilio-related Wiremock stub mappings."""
    return [
        StubMapping(
            name="twilio_send_message",
            request={
                "method": "POST",
                "urlPathPattern": "/2010-04-01/Accounts/[a-zA-Z0-9]+/Messages\\.json",
            },
            response={
                "status": 201,
                "headers": {"Content-Type": "application/json"},
                "jsonBody": {
                    "sid": "SM2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d",
                    "account_sid": "AC00000000000000000000000000000000",
                    "to": "+15551234567",
                    "from": "+15559876543",
                    "body": "Test message",
                    "status": "queued",
                    "direction": "outbound-api",
                    "date_created": "Thu, 01 Jan 2026 00:00:00 +0000",
                    "price": None,
                    "error_code": None,
                    "error_message": None,
                    "uri": "/2010-04-01/Accounts/AC00000000000000000000000000000000/Messages/SM2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d.json",
                },
            },
            priority=1,
        ),
    ]


twilio_stub = StubConfig(
    service_name="twilio",
    base_url_pattern="/2010-04-01",
    description="Twilio SMS API stubs (send message)",
    mappings=_twilio_stubs(),
)

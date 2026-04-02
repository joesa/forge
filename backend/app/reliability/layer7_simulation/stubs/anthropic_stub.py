"""
Anthropic API stubs for Wiremock simulation.

Covers:
  - POST /v1/messages → message response with text content
"""

from __future__ import annotations

from app.reliability.layer7_simulation.stub_registry import StubConfig, StubMapping


def _anthropic_stubs() -> list[StubMapping]:
    """Return all Anthropic-related Wiremock stub mappings."""
    return [
        StubMapping(
            name="anthropic_messages",
            request={
                "method": "POST",
                "urlPathPattern": "/v1/messages",
            },
            response={
                "status": 200,
                "headers": {"Content-Type": "application/json"},
                "jsonBody": {
                    "id": "msg_01Yg7HvKqW3nRs9tBp2xLm",
                    "type": "message",
                    "role": "assistant",
                    "content": [
                        {
                            "type": "text",
                            "text": "Test response",
                        },
                    ],
                    "model": "claude-sonnet-4-20250514",
                    "stop_reason": "end_turn",
                    "stop_sequence": None,
                    "usage": {
                        "input_tokens": 50,
                        "output_tokens": 100,
                    },
                },
            },
            priority=1,
        ),
    ]


anthropic_stub = StubConfig(
    service_name="anthropic",
    base_url_pattern="/v1",
    description="Anthropic Messages API stubs",
    mappings=_anthropic_stubs(),
)

"""
OpenAI API stubs for Wiremock simulation.

Covers:
  - POST /v1/chat/completions → chat completion response
  - POST /v1/embeddings       → embedding vector response
"""

from __future__ import annotations

from app.reliability.layer7_simulation.stub_registry import StubConfig, StubMapping

# Pre-computed 768-dimensional embedding vector (all 0.001 increments)
_MOCK_EMBEDDING: list[float] = [round(0.001 * i, 4) for i in range(768)]


def _openai_stubs() -> list[StubMapping]:
    """Return all OpenAI-related Wiremock stub mappings."""
    return [
        # ── POST /v1/chat/completions ────────────────────────────────
        StubMapping(
            name="openai_chat_completions",
            request={
                "method": "POST",
                "urlPathPattern": "/v1/chat/completions",
            },
            response={
                "status": 200,
                "headers": {"Content-Type": "application/json"},
                "jsonBody": {
                    "id": "chatcmpl-9Qf4mN8vCd2hLp7wXs3kR6",
                    "object": "chat.completion",
                    "created": 1234567890,
                    "model": "gpt-4o-mini",
                    "choices": [
                        {
                            "index": 0,
                            "message": {
                                "role": "assistant",
                                "content": "Test AI response",
                            },
                            "finish_reason": "stop",
                        },
                    ],
                    "usage": {
                        "prompt_tokens": 50,
                        "completion_tokens": 50,
                        "total_tokens": 100,
                    },
                },
            },
            priority=1,
        ),
        # ── POST /v1/embeddings ──────────────────────────────────────
        StubMapping(
            name="openai_embeddings",
            request={
                "method": "POST",
                "urlPathPattern": "/v1/embeddings",
            },
            response={
                "status": 200,
                "headers": {"Content-Type": "application/json"},
                "jsonBody": {
                    "object": "list",
                    "data": [
                        {
                            "object": "embedding",
                            "index": 0,
                            "embedding": _MOCK_EMBEDDING,
                        },
                    ],
                    "model": "text-embedding-3-small",
                    "usage": {
                        "prompt_tokens": 10,
                        "total_tokens": 10,
                    },
                },
            },
            priority=1,
        ),
    ]


openai_stub = StubConfig(
    service_name="openai",
    base_url_pattern="/v1",
    description="OpenAI API stubs (chat completions, embeddings)",
    mappings=_openai_stubs(),
)

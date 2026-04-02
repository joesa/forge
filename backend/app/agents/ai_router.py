"""
AI Router — abstraction layer for LLM calls.

Routes completion requests to the user's configured model provider
(Anthropic / OpenAI). In tests this is replaced with a mock that
returns pre-built JSON responses.

Temperature note:
  - C-Suite agents (Stage 2): temperature=0.7 (analytical, not code gen)
  - Build agents (Stage 6): temperature=0, fixed seed (AGENTS.md rule #4)
"""

from __future__ import annotations

import json
from typing import Any, Protocol

import structlog

logger = structlog.get_logger(__name__)


class AIRouterProtocol(Protocol):
    """Protocol that any AI router implementation must satisfy."""

    async def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.7,
        response_format: str = "json",
    ) -> str:
        """Send a completion request and return raw text response."""
        ...


class AIRouter:
    """Default AI router — dispatches to configured LLM provider.

    In the current implementation this returns stub JSON responses.
    Production will route to Anthropic/OpenAI via the user's API keys.
    """

    def __init__(self, provider: str = "stub") -> None:
        self.provider = provider

    async def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.7,
        response_format: str = "json",
    ) -> str:
        """Route completion to the configured provider.

        Returns raw text (expected to be JSON for agent calls).
        """
        logger.debug(
            "ai_router.complete",
            provider=self.provider,
            temperature=temperature,
            prompt_length=len(user_prompt),
        )

        if self.provider == "stub":
            return await self._stub_complete(system_prompt, user_prompt)

        # TODO: Production routing to Anthropic/OpenAI
        # This will be implemented when we integrate real API keys
        logger.warning("ai_router.no_provider", provider=self.provider)
        return "{}"

    async def _stub_complete(
        self,
        system_prompt: str,
        user_prompt: str,
    ) -> str:
        """Return a minimal valid JSON stub for testing."""
        # The stub returns an empty JSON object — each agent provides
        # its own defaults when parsing fails or returns incomplete data.
        return "{}"


def create_ai_router(provider: str = "stub") -> AIRouter:
    """Factory function for creating an AI router instance."""
    return AIRouter(provider=provider)

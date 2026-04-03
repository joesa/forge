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

    Automatically selects the provider based on available API keys:
      1. If provider="anthropic" (or ANTHROPIC_API_KEY is set): use Anthropic
      2. If provider="openai" (or OPENAI_API_KEY is set): use OpenAI
      3. Otherwise: stub (returns "{}" — agents use their _default_output())
    """

    def __init__(self, provider: str = "stub", api_key: str | None = None) -> None:
        self.provider = provider
        self.api_key = api_key

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

        if self.provider == "anthropic":
            return await self._anthropic_complete(system_prompt, user_prompt, temperature)

        if self.provider == "openai":
            return await self._openai_complete(system_prompt, user_prompt, temperature)

        if self.provider == "stub":
            return await self._stub_complete(system_prompt, user_prompt)

        logger.warning("ai_router.no_provider", provider=self.provider)
        return "{}"

    async def _anthropic_complete(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float,
    ) -> str:
        """Call Anthropic Claude API and return the text response."""
        from anthropic import AsyncAnthropic

        client = AsyncAnthropic(api_key=self.api_key)
        message = await client.messages.create(
            model="claude-opus-4-6",
            max_tokens=4096,
            temperature=temperature,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )
        return message.content[0].text  # type: ignore[union-attr]

    async def _openai_complete(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float,
    ) -> str:
        """Call OpenAI API and return the text response."""
        from openai import AsyncOpenAI

        client = AsyncOpenAI(api_key=self.api_key)
        response = await client.chat.completions.create(
            model="gpt-4o",
            temperature=temperature,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        return response.choices[0].message.content or "{}"

    async def _stub_complete(
        self,
        system_prompt: str,
        user_prompt: str,
    ) -> str:
        """Return a minimal valid JSON stub for testing."""
        # The stub returns an empty JSON object — each agent provides
        # its own defaults when parsing fails or returns incomplete data.
        return "{}"


def create_ai_router(provider: str | None = None, api_key: str | None = None) -> AIRouter:
    """Factory that auto-detects the best available provider.

    Priority order:
      1. Explicit provider + api_key arguments
      2. ANTHROPIC_API_KEY environment variable / settings
      3. OPENAI_API_KEY environment variable / settings
      4. Stub (no real API calls — agents use _default_output())
    """
    if provider is not None:
        # Explicit override — used in tests (provider="stub") and scripts
        return AIRouter(provider=provider, api_key=api_key)

    # Auto-detect from settings
    from app.config import settings

    if settings.ANTHROPIC_API_KEY:
        logger.debug("ai_router.auto_select", provider="anthropic")
        return AIRouter(provider="anthropic", api_key=settings.ANTHROPIC_API_KEY)

    if settings.OPENAI_API_KEY:
        logger.debug("ai_router.auto_select", provider="openai")
        return AIRouter(provider="openai", api_key=settings.OPENAI_API_KEY)

    logger.warning(
        "ai_router.no_api_key",
        detail="No ANTHROPIC_API_KEY or OPENAI_API_KEY configured — using stub",
    )
    return AIRouter(provider="stub")

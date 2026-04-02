"""
Layer 10 — Fallback cascade for AI providers.

Tries the preferred LLM provider first; if it returns a rate limit
(429) or other error, automatically falls through to the next available
provider.  Ensures build pipeline never stalls due to a single provider
outage.

Provider priority: anthropic → openai → gemini → mistral → cohere

Logs every fallback attempt for billing attribution.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

import structlog

logger = structlog.get_logger(__name__)


# ── Provider priority order ──────────────────────────────────────────

PROVIDER_PRIORITY: list[str] = [
    "anthropic",
    "openai",
    "gemini",
    "mistral",
    "cohere",
]


# ── Types ────────────────────────────────────────────────────────────


class RateLimitError(Exception):
    """Raised when a provider returns HTTP 429."""

    def __init__(self, provider: str, message: str = "") -> None:
        self.provider = provider
        super().__init__(f"Rate limited by {provider}: {message}")


class ProviderError(Exception):
    """Raised when a provider returns a non-retryable error."""

    def __init__(self, provider: str, message: str = "") -> None:
        self.provider = provider
        super().__init__(f"Provider error from {provider}: {message}")


class BuildAgentError(Exception):
    """Raised when ALL providers fail."""

    def __init__(
        self,
        message: str,
        attempts: list[dict[str, str]] | None = None,
    ) -> None:
        self.attempts = attempts or []
        super().__init__(message)


@dataclass
class FallbackAttempt:
    """Record of a single provider attempt."""

    provider: str
    success: bool = False
    error: str = ""
    error_type: str = ""


@dataclass
class FallbackLog:
    """Full log of all attempts in a fallback cascade."""

    attempts: list[FallbackAttempt] = field(default_factory=list)
    final_provider: str = ""
    fallback_count: int = 0


# ── Provider protocol ───────────────────────────────────────────────


class ProviderCallable(Protocol):
    """Protocol for provider-specific completion calls."""

    async def __call__(
        self,
        prompt: str,
        provider: str,
        **kwargs: Any,
    ) -> str:
        ...


# ── Default provider caller ─────────────────────────────────────────


class DefaultProviderCaller:
    """Default implementation that calls providers via a router.

    In tests, this is replaced with a mock that simulates rate limits.
    """

    def __init__(self, ai_router: Any | None = None) -> None:
        self._router = ai_router

    async def __call__(
        self,
        prompt: str,
        provider: str,
        **kwargs: Any,
    ) -> str:
        if self._router is None:
            raise ProviderError(provider, "No AI router configured")

        # The router is expected to dispatch to the correct provider
        # based on the provider parameter
        return await self._router.complete(
            system_prompt=kwargs.get("system_prompt", ""),
            user_prompt=prompt,
            temperature=kwargs.get("temperature", 0.0),
        )


# ── Public API ───────────────────────────────────────────────────────


async def call_with_fallback(
    prompt: str,
    preferred_provider: str,
    user_providers: dict[str, bool],
    *,
    caller: ProviderCallable | None = None,
    system_prompt: str = "",
    temperature: float = 0.0,
    fallback_log: FallbackLog | None = None,
) -> str:
    """Call an LLM with automatic multi-provider fallback.

    Parameters
    ----------
    prompt : str
        The user prompt to send.
    preferred_provider : str
        The provider to try first.
    user_providers : dict[str, bool]
        Mapping of provider name → enabled flag.
        Only providers with True are considered.
    caller : ProviderCallable | None
        The function that actually calls the provider.
        In production, this wraps the AI router.
    system_prompt : str
        System prompt to pass to the provider.
    temperature : float
        Temperature for the completion call.
    fallback_log : FallbackLog | None
        Optional mutable log object. When provided, it is populated
        with per-attempt details (provider, success, error) so the
        caller can attribute costs to the provider that actually served
        the request.

    Returns
    -------
    str
        The LLM response text.

    Raises
    ------
    BuildAgentError
        If all available providers fail.
    """
    if caller is None:
        raise BuildAgentError(
            "No provider caller configured",
            attempts=[],
        )

    # Build ordered list: preferred first, then by priority
    ordered: list[str] = []

    # Add preferred provider first (if enabled)
    if user_providers.get(preferred_provider, False):
        ordered.append(preferred_provider)

    # Add remaining providers in priority order
    for provider in PROVIDER_PRIORITY:
        if provider not in ordered and user_providers.get(provider, False):
            ordered.append(provider)

    if not ordered:
        raise BuildAgentError(
            "No enabled providers available",
            attempts=[],
        )

    log = fallback_log if fallback_log is not None else FallbackLog()
    all_attempt_dicts: list[dict[str, str]] = []

    for provider in ordered:
        attempt = FallbackAttempt(provider=provider)

        try:
            logger.info(
                "fallback_cascade.trying_provider",
                provider=provider,
                is_preferred=(provider == preferred_provider),
            )

            response = await caller(
                prompt,
                provider,
                system_prompt=system_prompt,
                temperature=temperature,
            )

            attempt.success = True
            log.attempts.append(attempt)
            log.final_provider = provider
            log.fallback_count = len(log.attempts) - 1

            if log.fallback_count > 0:
                logger.warning(
                    "fallback_cascade.used_fallback",
                    preferred=preferred_provider,
                    actual=provider,
                    fallback_count=log.fallback_count,
                )
            else:
                logger.info(
                    "fallback_cascade.primary_succeeded",
                    provider=provider,
                )

            return response

        except RateLimitError as exc:
            attempt.error = str(exc)
            attempt.error_type = "rate_limit"
            log.attempts.append(attempt)
            all_attempt_dicts.append({
                "provider": provider,
                "error": str(exc),
                "type": "rate_limit",
            })

            logger.warning(
                "fallback_cascade.rate_limited",
                provider=provider,
                error=str(exc),
            )
            continue

        except ProviderError as exc:
            attempt.error = str(exc)
            attempt.error_type = "provider_error"
            log.attempts.append(attempt)
            all_attempt_dicts.append({
                "provider": provider,
                "error": str(exc),
                "type": "provider_error",
            })

            logger.warning(
                "fallback_cascade.provider_error",
                provider=provider,
                error=str(exc),
            )
            continue

        except Exception as exc:
            attempt.error = str(exc)
            attempt.error_type = "unknown"
            log.attempts.append(attempt)
            all_attempt_dicts.append({
                "provider": provider,
                "error": str(exc),
                "type": "unknown",
            })

            logger.error(
                "fallback_cascade.unexpected_error",
                provider=provider,
                error=str(exc),
            )
            continue

    # All providers failed
    raise BuildAgentError(
        f"All {len(ordered)} providers failed: "
        f"{', '.join(ordered)}",
        attempts=all_attempt_dicts,
    )

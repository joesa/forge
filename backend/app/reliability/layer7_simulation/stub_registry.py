"""
Stub registry — maps service names to their Wiremock stub configurations.

Each stub is a StubConfig containing Wiremock-compatible JSON mappings
that get POSTed to Wiremock's ``/__admin/mappings`` endpoint.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import structlog

logger = structlog.get_logger(__name__)


@dataclass(frozen=True)
class StubMapping:
    """A single Wiremock stub mapping (request → response)."""

    name: str
    request: dict[str, object]
    response: dict[str, object]
    priority: int = 5


@dataclass(frozen=True)
class StubConfig:
    """Complete stub configuration for one external service."""

    service_name: str
    base_url_pattern: str
    description: str
    mappings: list[StubMapping] = field(default_factory=list)


# ── Service stub imports ─────────────────────────────────────────────
# Lazy-loaded to avoid circular imports and keep registry clean.

def _load_stripe() -> StubConfig:
    from app.reliability.layer7_simulation.stubs.stripe_stub import stripe_stub
    return stripe_stub


def _load_supabase() -> StubConfig:
    from app.reliability.layer7_simulation.stubs.supabase_stub import supabase_stub
    return supabase_stub


def _load_resend() -> StubConfig:
    from app.reliability.layer7_simulation.stubs.resend_stub import resend_stub
    return resend_stub


def _load_openai() -> StubConfig:
    from app.reliability.layer7_simulation.stubs.openai_stub import openai_stub
    return openai_stub


def _load_anthropic() -> StubConfig:
    from app.reliability.layer7_simulation.stubs.anthropic_stub import anthropic_stub
    return anthropic_stub


def _load_twilio() -> StubConfig:
    from app.reliability.layer7_simulation.stubs.twilio_stub import twilio_stub
    return twilio_stub


# ── Registry ─────────────────────────────────────────────────────────
# Maps service name → loader function (lazy).  We call the loader only
# when the stub is actually requested so import-time is fast.

_REGISTRY: dict[str, type[None] | object] = {
    "stripe": _load_stripe,
    "supabase": _load_supabase,
    "resend": _load_resend,
    "openai": _load_openai,
    "anthropic": _load_anthropic,
    "twilio": _load_twilio,
}

SUPPORTED_SERVICES: list[str] = list(_REGISTRY.keys())


def get_stub(service_name: str) -> StubConfig:
    """Retrieve the stub configuration for a named service.

    Raises ``KeyError`` if the service is not in the registry.
    """
    loader = _REGISTRY.get(service_name)
    if loader is None:
        available = ", ".join(sorted(SUPPORTED_SERVICES))
        raise KeyError(
            f"Unknown service '{service_name}'. Available: {available}"
        )
    # loader is actually a callable (function), call it
    stub = loader()  # type: ignore[operator]
    logger.debug("stub_registry.loaded", service=service_name, mappings=len(stub.mappings))
    return stub


def get_all_stubs(services: list[str]) -> list[StubConfig]:
    """Retrieve stub configs for multiple services.

    Unknown services are logged as warnings and skipped rather than
    raising — the build pipeline should not crash on an unknown
    integration, it should degrade gracefully.
    """
    stubs: list[StubConfig] = []
    for svc in services:
        try:
            stubs.append(get_stub(svc))
        except KeyError:
            logger.warning(
                "stub_registry.unknown_service_skipped",
                service=svc,
                available=SUPPORTED_SERVICES,
            )
    return stubs

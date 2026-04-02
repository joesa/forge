# ruff: noqa: F401
"""
Layer 7 — External service simulation (Wiremock).

Intercepts all external API calls during testing and smoke tests so
the build pipeline NEVER calls real services.  Architecture rule #7:
"Never call real external APIs in tests — Wiremock stubs only."

Components:
  - WiremockManager: lifecycle management (start / configure / verify / stop)
  - StubRegistry: maps service names to stub configurations
  - stubs/: per-service stub definitions (Stripe, Supabase, Resend, etc.)
"""

from app.reliability.layer7_simulation.wiremock_manager import (
    VerificationReport,
    WiremockManager,
)
from app.reliability.layer7_simulation.stub_registry import (
    StubConfig,
    get_all_stubs,
    get_stub,
)

__all__ = [
    "StubConfig",
    "VerificationReport",
    "WiremockManager",
    "get_all_stubs",
    "get_stub",
]

# ruff: noqa: F401
"""
Layer 10 — AI agent reliability.

Ensures predictable, deterministic, and resilient LLM interactions:

  1. Context window manager — chunking + merging for large contexts
  2. CSS validator — detects invalid Tailwind classes in generated TSX
  3. Determinism enforcer — forces temperature=0, seed=42 on build agents
  4. Fallback cascade — multi-provider failover (anthropic → openai → gemini → …)
"""

from app.reliability.layer10_ai.context_window_manager import (
    ContextWindowManager,
)
from app.reliability.layer10_ai.css_validator import (
    CSSValidationReport,
    validate_css_classes,
)
from app.reliability.layer10_ai.determinism_enforcer import (
    enforce_determinism,
)
from app.reliability.layer10_ai.fallback_cascade import (
    BuildAgentError,
    FallbackLog,
    call_with_fallback,
)

__all__ = [
    "BuildAgentError",
    "CSSValidationReport",
    "ContextWindowManager",
    "FallbackLog",
    "call_with_fallback",
    "enforce_determinism",
    "validate_css_classes",
]

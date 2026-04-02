# ruff: noqa: F401
"""
Layer 9 — Resilience and recovery.

Provides automated failure recovery:

  1. Hotfix agent — targeted AI-driven repair of gate failures (max 3 attempts)
  2. Rollback engine — restores last known-good build from R2
  3. Canary deploy — phased traffic migration (5% → 25% → 100%) with auto-rollback
  4. Migration safety — blocks destructive SQL operations (DROP TABLE, DELETE w/o WHERE)
"""

from app.reliability.layer9_resilience.hotfix_agent import (
    HotfixContext,
    HotfixChange,
    HotfixResult,
    apply_hotfix,
)
from app.reliability.layer9_resilience.rollback_engine import (
    RollbackResult,
    rollback_to_last_good_build,
)
from app.reliability.layer9_resilience.canary_deploy import (
    CanaryPhase,
    CanaryResult,
    deploy_canary,
)
from app.reliability.layer9_resilience.migration_safety import (
    DestructiveOp,
    SafetyReport,
    check_migration_safety,
)

__all__ = [
    "CanaryPhase",
    "CanaryResult",
    "DestructiveOp",
    "HotfixChange",
    "HotfixContext",
    "HotfixResult",
    "RollbackResult",
    "SafetyReport",
    "apply_hotfix",
    "check_migration_safety",
    "deploy_canary",
    "rollback_to_last_good_build",
]

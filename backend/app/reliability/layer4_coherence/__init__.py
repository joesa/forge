# ruff: noqa: F401
"""
Layer 4 — File coherence engine.

Runs AFTER all 10 build agents complete (Architecture rule #5).
Validates import/export consistency, barrel re-exports, and seam integrity.
Auto-fixes minor issues (typos, case mismatches); escalates critical errors.
"""

from app.reliability.layer4_coherence.barrel_validator import (
    BarrelReport,
    validate_barrel,
)
from app.reliability.layer4_coherence.file_coherence_engine import (
    CoherenceCheckReport,
    run_coherence_check,
)
from app.reliability.layer4_coherence.seam_checker import (
    SeamReport,
    check_seam,
)

__all__ = [
    "BarrelReport",
    "CoherenceCheckReport",
    "SeamReport",
    "check_seam",
    "run_coherence_check",
    "validate_barrel",
]

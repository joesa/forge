# ruff: noqa: F401
"""
Layer 8 — Post-build verification tools.

Runs inside ReviewAgent (agent 10) AFTER the app is built and running.
Provides six verification stages:

  1. Visual regression — Playwright screenshots, pixelmatch diffing
  2. SAST scanner — Semgrep + detect-secrets for security findings
  3. Performance budget — Lighthouse CI audits against thresholds
  4. Accessibility audit — axe-core injection via Playwright (WCAG 2.1 AA)
  5. Dead code detector — ts-prune for unused exports/imports (warning only)
  6. Seed generator — Faker-based realistic seed data for sandbox DBs

Execution order matters: screenshots first (baseline), security, perf,
a11y, dead code (non-blocking), then seeds for smoke tests.
"""

from app.reliability.layer8_verification.visual_regression import (
    VisualRegressionReport,
    run_visual_regression,
)
from app.reliability.layer8_verification.sast_scanner import (
    Finding,
    SASTReport,
    run_sast_scan,
)
from app.reliability.layer8_verification.perf_budget import (
    PerfReport,
    run_perf_audit,
)
from app.reliability.layer8_verification.accessibility_audit import (
    A11yReport,
    run_a11y_audit,
)
from app.reliability.layer8_verification.dead_code_detector import (
    DeadCodeReport,
    detect_dead_code,
)
from app.reliability.layer8_verification.seed_generator import (
    SeedReport,
    generate_and_apply_seeds,
)

__all__ = [
    "A11yReport",
    "DeadCodeReport",
    "Finding",
    "PerfReport",
    "SASTReport",
    "SeedReport",
    "VisualRegressionReport",
    "detect_dead_code",
    "generate_and_apply_seeds",
    "run_a11y_audit",
    "run_perf_audit",
    "run_sast_scan",
    "run_visual_regression",
]

"""
Review Agent (Agent 10) — THE CRITICAL FINAL AGENT.

Does NOT generate application code. Runs all final validation gates.

Steps:
  1. Layer 4 — file coherence (hotfix attempt if critical errors)
  2. Gate G8 — full build verification (tsc, eslint, build, smoke)
  3. Gate G11 — SAST security scan (Semgrep + Bandit)
  4. Gate G12 — visual regression (Playwright screenshots → R2)
  5. Layer 8 — post-build checks (Lighthouse, axe, dead code, seeds)
  6. Capture final snapshot

Returns ReviewResult with all gate outcomes and build status.
"""

from __future__ import annotations

import time
from typing import Any

import structlog
from pydantic import BaseModel, Field

from app.agents.ai_router import AIRouter
from app.agents.build.context_window_manager import ContextWindowManager
from app.agents.build.hotfix_agent import HotfixResult, run_hotfix_agent
from app.agents.build.sandbox_runner import (
    AxeResult,
    LighthouseResult,
    PlaywrightResult,
    SemgrepResult,
    ToolResult,
    run_axe_audit,
    run_bandit,
    run_build,
    run_dead_code_check,
    run_eslint,
    run_lighthouse,
    run_playwright,
    run_seed_generator,
    run_semgrep,
    run_smoke_test,
    run_tsc_check,
)
from app.agents.build.snapshot_service import SnapshotService
from app.agents.state import PipelineState
from app.reliability.layer4_coherence import run_coherence_check

logger = structlog.get_logger(__name__)

AGENT_NAME = "review"


class ReviewStepResult(BaseModel):
    """Result of a single review step."""
    step_name: str
    passed: bool
    details: str = ""
    duration_ms: int = 0


class ReviewResult(BaseModel):
    """Complete result from the review agent."""
    build_status: str = Field(
        description="'COMPLETED' or 'FAILED'"
    )
    all_passed: bool = False
    steps: list[ReviewStepResult] = Field(default_factory=list)
    hotfix_attempted: bool = False
    hotfix_result: HotfixResult | None = None
    coherence_report: dict[str, Any] = Field(default_factory=dict)
    security_scan: dict[str, Any] = Field(default_factory=dict)
    lighthouse_metrics: dict[str, Any] = Field(default_factory=dict)
    screenshots: list[str] = Field(default_factory=list)
    total_duration_ms: int = 0


async def run_review_agent(
    state: PipelineState,
    ai_router: AIRouter,
    context_window_manager: ContextWindowManager,
) -> ReviewResult:
    """Run all final validation gates. Does NOT generate app code.

    Architecture rule #5: File coherence engine runs AFTER all build agents.
    """
    start = time.monotonic()
    generated_files = dict(state.get("generated_files", {}))
    build_id = state.get("build_id", state.get("pipeline_id", "unknown"))
    project_id = state.get("project_id", "unknown")
    sandbox_id = state.get("sandbox_id", "") or "stub-sandbox"
    steps: list[ReviewStepResult] = []
    all_passed = True

    logger.info(
        "review_agent.start",
        build_id=build_id,
        file_count=len(generated_files),
    )

    # ── Step 1: Layer 4 — File coherence ─────────────────────────
    step_start = time.monotonic()
    coherence_report = await run_coherence_check(
        str(build_id), generated_files
    )
    coherence_dict = coherence_report.model_dump()
    step_ms = int((time.monotonic() - step_start) * 1000)

    coherence_passed = coherence_report.all_passed
    hotfix_attempted = False
    hotfix_result: HotfixResult | None = None

    if not coherence_passed and coherence_report.critical_errors > 0:
        # Attempt hotfix
        logger.warning(
            "review_agent.coherence_failed_attempting_hotfix",
            critical_errors=coherence_report.critical_errors,
        )
        hotfix_attempted = True
        hotfix_result = await run_hotfix_agent(
            state=state,
            ai_router=ai_router,
            context_window_manager=context_window_manager,
            failed_agent="coherence",
            error_details=f"{coherence_report.critical_errors} critical coherence errors",
            generated_files=generated_files,
        )

        if hotfix_result.success:
            # Re-run coherence after hotfix
            coherence_report = await run_coherence_check(
                str(build_id), generated_files
            )
            coherence_dict = coherence_report.model_dump()
            coherence_passed = coherence_report.all_passed

    steps.append(ReviewStepResult(
        step_name="file_coherence",
        passed=coherence_passed,
        details=(
            f"files_checked={coherence_report.files_checked}, "
            f"critical={coherence_report.critical_errors}, "
            f"auto_fixed={coherence_report.auto_fixes_applied}"
        ),
        duration_ms=step_ms,
    ))
    if not coherence_passed:
        all_passed = False

    # ── Step 2: Gate G8 — Full build verification ────────────────
    step_start = time.monotonic()

    tsc_result = await run_tsc_check(sandbox_id, generated_files)
    eslint_result = await run_eslint(sandbox_id, generated_files)
    build_result = await run_build(sandbox_id, generated_files)

    # Extract route paths for smoke test
    routes = ["/"]
    for fp in generated_files:
        if "/pages/" in fp or "/page.tsx" in fp:
            route = "/" + fp.split("/pages/")[-1].replace(".tsx", "").replace("/page", "").replace("index", "")
            routes.append(route)
    routes = list(set(routes))

    smoke_result = await run_smoke_test(sandbox_id, routes)

    g8_passed = all(r.passed for r in [tsc_result, eslint_result, build_result, smoke_result])
    step_ms = int((time.monotonic() - step_start) * 1000)

    steps.append(ReviewStepResult(
        step_name="build_verification",
        passed=g8_passed,
        details=(
            f"tsc={tsc_result.passed}, eslint={eslint_result.passed}, "
            f"build={build_result.passed}, smoke={smoke_result.passed}"
        ),
        duration_ms=step_ms,
    ))
    if not g8_passed:
        all_passed = False

    # ── Step 3: Gate G11 — SAST security scan ────────────────────
    step_start = time.monotonic()

    semgrep_result = await run_semgrep(sandbox_id, generated_files)
    bandit_result = await run_bandit(sandbox_id, generated_files)

    sast_passed = semgrep_result.passed and bandit_result.passed
    security_scan = {
        "semgrep": {
            "passed": semgrep_result.passed,
            "findings": len(semgrep_result.findings),
            "critical": semgrep_result.critical_count,
            "high": semgrep_result.high_count,
        },
        "bandit": {"passed": bandit_result.passed},
    }
    step_ms = int((time.monotonic() - step_start) * 1000)

    steps.append(ReviewStepResult(
        step_name="sast_security",
        passed=sast_passed,
        details=f"semgrep={semgrep_result.passed}, bandit={bandit_result.passed}",
        duration_ms=step_ms,
    ))
    if not sast_passed:
        all_passed = False

    # ── Step 4: Gate G12 — Visual regression ─────────────────────
    step_start = time.monotonic()

    playwright_result = await run_playwright(sandbox_id, routes, str(build_id))
    screenshots = [s.screenshot_url for s in playwright_result.screenshots]
    step_ms = int((time.monotonic() - step_start) * 1000)

    steps.append(ReviewStepResult(
        step_name="visual_regression",
        passed=playwright_result.passed,
        details=f"screenshots={len(screenshots)}",
        duration_ms=step_ms,
    ))
    if not playwright_result.passed:
        all_passed = False

    # ── Step 5: Layer 8 — Post-build checks ──────────────────────
    step_start = time.monotonic()

    lighthouse_result = await run_lighthouse(sandbox_id)
    axe_result = await run_axe_audit(sandbox_id)
    dead_code_result = await run_dead_code_check(sandbox_id, generated_files)

    # Seed generator — find DB schema
    db_schema = ""
    for fp, content in generated_files.items():
        if "schema.prisma" in fp or "models" in fp:
            db_schema = content
            break
    seed_result = await run_seed_generator(sandbox_id, db_schema)

    layer8_passed = all(r.passed for r in [lighthouse_result, axe_result, dead_code_result, seed_result])
    lighthouse_metrics = lighthouse_result.metrics.model_dump()
    step_ms = int((time.monotonic() - step_start) * 1000)

    steps.append(ReviewStepResult(
        step_name="post_build_checks",
        passed=layer8_passed,
        details=(
            f"lighthouse={lighthouse_result.passed}, "
            f"a11y={axe_result.passed}, "
            f"dead_code={dead_code_result.passed}, "
            f"seeds={seed_result.passed}"
        ),
        duration_ms=step_ms,
    ))
    if not layer8_passed:
        all_passed = False

    # ── Step 6: Capture final snapshot ───────────────────────────
    step_start = time.monotonic()
    snapshot_service = SnapshotService()
    snapshot_url = await snapshot_service.capture_snapshot(
        build_id=str(build_id),
        project_id=str(project_id),
        agent_name=AGENT_NAME,
        snapshot_index=10,
        generated_files=generated_files,
        gate_results=state.get("gate_results", {}),
    )
    step_ms = int((time.monotonic() - step_start) * 1000)

    steps.append(ReviewStepResult(
        step_name="final_snapshot",
        passed=bool(snapshot_url),
        details=f"r2_key={snapshot_url}",
        duration_ms=step_ms,
    ))

    # ── Build final result ───────────────────────────────────────
    total_ms = int((time.monotonic() - start) * 1000)
    build_status = "COMPLETED" if all_passed else "FAILED"

    result = ReviewResult(
        build_status=build_status,
        all_passed=all_passed,
        steps=steps,
        hotfix_attempted=hotfix_attempted,
        hotfix_result=hotfix_result,
        coherence_report=coherence_dict,
        security_scan=security_scan,
        lighthouse_metrics=lighthouse_metrics,
        screenshots=screenshots,
        total_duration_ms=total_ms,
    )

    logger.info(
        "review_agent.complete",
        build_status=build_status,
        all_passed=all_passed,
        steps_total=len(steps),
        steps_passed=sum(1 for s in steps if s.passed),
        elapsed_ms=total_ms,
    )

    return result

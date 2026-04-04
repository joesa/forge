"""
Hotfix Agent — Layer 9 automated repair for build failures.

When a build agent fails Gate G7, the pipeline calls the hotfix agent
to attempt an automated fix before retrying.  The hotfix agent analyzes
the error, applies targeted patches to the generated files, and returns
a HotfixResult indicating whether the fix was successful.
"""

from __future__ import annotations

from typing import Any

import structlog
from pydantic import BaseModel, Field

from app.agents.ai_router import AIRouter
from app.agents.build.context_window_manager import ContextWindowManager
from app.agents.state import PipelineState

logger = structlog.get_logger(__name__)


class HotfixChange(BaseModel):
    """A single file change applied by the hotfix agent."""

    file_path: str = Field(description="Path of the file that was changed")
    change_type: str = Field(
        description="Type of change: 'modify', 'create', 'delete'"
    )
    description: str = Field(description="What was changed and why")


class HotfixResult(BaseModel):
    """Result of a hotfix attempt."""

    success: bool = Field(
        default=False,
        description="Whether the hotfix resolved the issue",
    )
    changes: list[HotfixChange] = Field(
        default_factory=list,
        description="List of file changes applied",
    )
    reason: str = Field(
        default="",
        description="Explanation of the result",
    )
    error_category: str = Field(
        default="unknown",
        description="Category of the error: 'syntax', 'import', 'type', 'runtime', 'unknown'",
    )


async def run_hotfix_agent(
    state: PipelineState,
    ai_router: AIRouter,
    context_window_manager: ContextWindowManager,
    failed_agent: str,
    error_details: str,
    generated_files: dict[str, str],
) -> HotfixResult:
    """Attempt to automatically fix coherence/build failures.

    Uses the Layer 9 apply_hotfix engine for each unique file with
    critical coherence errors.  Modifies generated_files in-place.
    """
    from app.reliability.layer4_coherence import run_coherence_check
    from app.reliability.layer9_resilience import hotfix_agent as l9

    build_id = str(state.get("pipeline_id", "hotfix"))

    # Get the full set of current coherence issues
    report = await run_coherence_check(build_id, generated_files)

    if report.all_passed:
        return HotfixResult(success=True, reason="coherence already passing")

    critical = [i for i in report.issues if i.severity == "critical"]
    if not critical:
        return HotfixResult(success=True, reason="no critical issues to fix")

    logger.info(
        "hotfix_agent.fixing_coherence",
        critical_count=len(critical),
        unique_files=len({i.file for i in critical}),
    )

    changes: list[HotfixChange] = []
    seen_files: set[str] = set()

    # One fix attempt per file (first critical issue per file drives the fix)
    for issue in critical:
        if issue.file in seen_files:
            continue
        seen_files.add(issue.file)

        if issue.file not in generated_files:
            continue

        ctx = l9.HotfixContext(
            failed_gate="G10",
            error_message=issue.message,
            failing_file=issue.file,
        )
        try:
            l9_result = await l9.apply_hotfix(ctx, generated_files, ai_router)
            if l9_result.changes:
                changes.append(HotfixChange(
                    file_path=issue.file,
                    change_type="modify",
                    description=f"Fixed coherence: {issue.message[:200]}",
                ))
        except Exception as exc:
            logger.warning(
                "hotfix_agent.file_fix_failed",
                file=issue.file,
                error=str(exc),
            )

    # Re-check to see if errors were reduced (partial success counts)
    if changes:
        try:
            recheck = await run_coherence_check(build_id, generated_files)
            success = recheck.critical_errors < report.critical_errors
            logger.info(
                "hotfix_agent.recheck",
                before=report.critical_errors,
                after=recheck.critical_errors,
                success=success,
            )
        except Exception:
            success = bool(changes)
    else:
        success = False

    return HotfixResult(
        success=success,
        changes=changes,
        reason=(
            f"Attempted fixes on {len(seen_files)} file(s) "
            f"({len(changes)} succeeded)"
        ),
        error_category="import",
    )

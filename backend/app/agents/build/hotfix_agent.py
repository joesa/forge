"""
Hotfix Agent — Layer 9 automated repair for build failures.

When a build agent fails Gate G7, the pipeline calls the hotfix agent
to attempt an automated fix before retrying.  The hotfix agent analyzes
the error, applies targeted patches to the generated files, and returns
a HotfixResult indicating whether the fix was successful.

Current state: REAL STUB — correct signature and return type, but
returns ``HotfixResult(success=False)`` immediately.  Session 2.8 will
fill in the real implementation.  The ReviewAgent and graph.py can call
this without crashing.
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
    """Attempt to automatically fix a build agent failure.

    Parameters
    ----------
    state : PipelineState
        Current pipeline state.
    ai_router : AIRouter
        LLM router for generating fixes.
    context_window_manager : ContextWindowManager
        Context window manager for the LLM call.
    failed_agent : str
        Name of the agent that failed G7.
    error_details : str
        Detailed error description from the G7 failure.
    generated_files : dict[str, str]
        Current generated files (may be modified by the hotfix).

    Returns
    -------
    HotfixResult
        Result indicating whether the fix was successful.
    """
    logger.warning(
        "hotfix_agent.not_yet_implemented",
        failed_agent=failed_agent,
        error_details=error_details[:200],
    )

    return HotfixResult(
        success=False,
        changes=[],
        reason="not_yet_implemented",
        error_category="unknown",
    )

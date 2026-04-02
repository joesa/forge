"""
PipelineState — the single TypedDict threaded through every LangGraph node.

Every field is optional (total=False) so nodes can incrementally build
the state as the pipeline progresses through stages 1→6.
"""

from __future__ import annotations

from typing import TypedDict


class GateResult(TypedDict):
    """Result of a single quality-gate check."""

    passed: bool
    reason: str


class IdeaSpec(TypedDict, total=False):
    """User's idea specification — the pipeline's input."""

    title: str
    description: str
    features: list[str]
    framework: str
    target_audience: str


class PipelineState(TypedDict, total=False):
    """
    Full pipeline state — flows through all 6 stages.

    Stages:
      1. Input Layer — validate idea, inject schema
      2. C-Suite Analysis — 8 parallel analyst agents
      3. Synthesis — merge analyses into comprehensive plan
      4. Spec Layer — 5 parallel spec agents
      5. Bootstrap — build manifest + cache check
      6. Build — 10 sequential code-gen agents
    """

    # ── Identity ─────────────────────────────────────────────────────
    pipeline_id: str
    project_id: str
    user_id: str
    current_stage: int  # 1-6

    # ── Input ────────────────────────────────────────────────────────
    idea_spec: dict[str, object]

    # ── Stage 2: C-Suite outputs (8 analysts) ────────────────────────
    csuite_outputs: dict[str, dict[str, object]]

    # ── Stage 3: Synthesizer output ──────────────────────────────────
    comprehensive_plan: dict[str, object]

    # ── Stage 4: Spec agent outputs (5 agents) ───────────────────────
    spec_outputs: dict[str, dict[str, object]]

    # ── Stage 5: Build manifest ──────────────────────────────────────
    build_manifest: dict[str, object]

    # ── Stage 6: Generated code ──────────────────────────────────────
    generated_files: dict[str, str]  # path → file content

    # ── Quality gates G1–G12 ─────────────────────────────────────────
    gate_results: dict[str, GateResult]

    # ── Error tracking ───────────────────────────────────────────────
    errors: list[str]

    # ── Sandbox ──────────────────────────────────────────────────────
    sandbox_id: str | None

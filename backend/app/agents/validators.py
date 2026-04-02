"""
Quality-gate validators G1–G12.

Each function inspects the current PipelineState and returns
``{"passed": bool, "reason": str}``.

Architecture rule #5: File coherence engine (G10) runs AFTER all
10 build agents, not per-agent.
"""

from __future__ import annotations

from app.agents.state import GateResult, PipelineState

# ── Helpers ──────────────────────────────────────────────────────────

_CSUITE_AGENTS = (
    "ceo", "cto", "cpo", "cdo", "ciso",
    "qa_lead", "devops_lead", "ux_lead",
)

_SPEC_AGENTS = (
    "api_spec", "db_spec", "ui_spec", "infra_spec", "test_spec",
)

_BUILD_AGENTS = (
    "prd", "design_system", "layout", "component", "page",
    "api", "state", "integration", "config", "quality",
)


def _ok(reason: str = "passed") -> GateResult:
    return {"passed": True, "reason": reason}


def _fail(reason: str) -> GateResult:
    return {"passed": False, "reason": reason}


# ── Stage 1 gates ────────────────────────────────────────────────────

def validate_g1(state: PipelineState) -> GateResult:
    """G1 — Validate IdeaSpec has required fields."""
    idea = state.get("idea_spec")
    if not idea:
        return _fail("idea_spec is missing")
    if not idea.get("title"):
        return _fail("idea_spec.title is required")
    if not idea.get("description"):
        return _fail("idea_spec.description is required")
    return _ok("idea_spec validated")


# ── Stage 2 gates ────────────────────────────────────────────────────

def validate_g2(state: PipelineState) -> GateResult:
    """G2 — All 8 C-suite agent outputs must be present."""
    outputs = state.get("csuite_outputs", {})
    missing = [a for a in _CSUITE_AGENTS if a not in outputs]
    if missing:
        return _fail(f"missing csuite outputs: {', '.join(missing)}")
    return _ok("all 8 csuite outputs present")


def validate_g3(state: PipelineState) -> GateResult:
    """G3 — Auto-resolve conflicts (always passes per spec)."""
    return _ok("conflicts auto-resolved")


# ── Stage 3 gates ────────────────────────────────────────────────────

def validate_g4(state: PipelineState) -> GateResult:
    """G4 — Comprehensive plan must have coherence_score >= 0.85."""
    plan = state.get("comprehensive_plan", {})
    if not plan:
        return _fail("comprehensive_plan is missing")
    score = plan.get("coherence_score", 0.0)
    if not isinstance(score, (int, float)):
        return _fail(f"coherence_score is not numeric: {score}")
    if score < 0.85:
        return _fail(f"coherence_score {score:.2f} < 0.85 threshold")
    return _ok(f"coherence_score {score:.2f} meets threshold")


# ── Stage 4 gates ────────────────────────────────────────────────────

def validate_g5(state: PipelineState) -> GateResult:
    """G5 — All 5 spec agent outputs must be present."""
    outputs = state.get("spec_outputs", {})
    missing = [a for a in _SPEC_AGENTS if a not in outputs]
    if missing:
        return _fail(f"missing spec outputs: {', '.join(missing)}")
    return _ok("all 5 spec outputs present")


# ── Stage 5 gates ────────────────────────────────────────────────────

def validate_g6(state: PipelineState) -> GateResult:
    """G6 — Build manifest must have a non-empty files list."""
    manifest = state.get("build_manifest", {})
    if not manifest:
        return _fail("build_manifest is missing")
    files = manifest.get("files")
    if not isinstance(files, list) or len(files) == 0:
        return _fail("build_manifest.files is missing or empty")
    return _ok(f"build_manifest has {len(files)} files")


# ── Stage 6 gates (per-agent + final) ───────────────────────────────

def validate_g7(state: PipelineState, agent_name: str | None = None) -> GateResult:
    """G7 — Per-build-agent validation: output exists and has no errors."""
    if agent_name is None:
        return _fail("agent_name is required for G7")
    outputs = state.get("generated_files", {})
    errors = state.get("errors", [])
    agent_errors = [e for e in errors if agent_name in e]
    if agent_errors:
        return _fail(f"agent {agent_name} produced errors: {agent_errors[0]}")
    # Check that the agent contributed at least one file
    agent_files = [p for p in outputs if agent_name in p or outputs.get(p)]
    if not agent_files and agent_name not in ("quality",):
        # quality agent may not produce files directly
        return _fail(f"agent {agent_name} produced no files")
    return _ok(f"agent {agent_name} passed")


def validate_g8(state: PipelineState) -> GateResult:
    """G8 — At least 5 generated files after build stage."""
    files = state.get("generated_files", {})
    if len(files) < 5:
        return _fail(f"only {len(files)} files generated, need >= 5")
    return _ok(f"{len(files)} files generated")


def validate_g9(state: PipelineState) -> GateResult:
    """G9 — No remaining errors after build stage."""
    errors = state.get("errors", [])
    if errors:
        return _fail(f"{len(errors)} errors remain: {errors[0]}")
    return _ok("no errors")


def validate_g10(state: PipelineState) -> GateResult:
    """G10 — File coherence check (runs AFTER all 10 build agents).

    Architecture rule #5: coherence engine runs after all build agents.
    Stub: checks that generated_files is non-empty.
    """
    files = state.get("generated_files", {})
    if not files:
        return _fail("no generated files for coherence check")
    # In production this runs the actual coherence engine
    return _ok(f"coherence check passed on {len(files)} files")


def validate_g11(state: PipelineState) -> GateResult:
    """G11 — Build manifest files match generated files."""
    manifest = state.get("build_manifest", {})
    generated = state.get("generated_files", {})
    expected_files = manifest.get("files", [])
    missing = [f for f in expected_files if f not in generated]
    if missing:
        return _fail(
            f"{len(missing)} manifest files not generated: {missing[0]}"
        )
    return _ok("all manifest files generated")


def validate_g12(state: PipelineState) -> GateResult:
    """G12 — Final pipeline validation: all previous gates passed."""
    gate_results = state.get("gate_results", {})
    failed = [
        gid for gid, result in gate_results.items()
        if not result.get("passed", False)
    ]
    if failed:
        return _fail(f"gates failed: {', '.join(failed)}")
    return _ok("all gates passed — pipeline complete")

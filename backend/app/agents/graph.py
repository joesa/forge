"""
LangGraph StateGraph — 6-stage FORGE build pipeline.

Stages:
  1. input_layer      → G1 + Layer 2 schema injection
  2. csuite_analysis   → 8 parallel agents via asyncio.gather  → G2, G3
  3. synthesis         → Synthesizer merges → comprehensive plan  → G4
  4. spec_layer        → 5 parallel spec agents                  → G5
  5. bootstrap         → BuildManifest + cache check             → G6
  6. build             → 10 sequential build agents, G7 each     → G8–G12

On each state change a Redis pub/sub event is published on channel
``pipeline:{pipeline_id}`` so WebSocket clients receive live updates.

Architecture rules enforced:
  #4: temperature=0, fixed seed (deterministic) — set in build agents (Stage 6)
      C-Suite agents (Stage 2) use temperature=0.7 (analytical, not code gen)
  #5: File coherence engine runs AFTER all 10 build agents
  #6: Schema injection happens BEFORE each relevant agent starts
"""

from __future__ import annotations

import asyncio
import time
from typing import Any

import structlog
from langgraph.graph import END, StateGraph

from app.agents.ai_router import AIRouter, create_ai_router
from app.agents.csuite import CSUITE_AGENT_MAP, CSUITE_AGENT_NAMES
from app.agents.state import PipelineState
from app.agents.synthesis.g3_resolver import run_g3_resolver
from app.agents.synthesis.synthesizer import run_synthesizer
from app.agents.validators import (
    validate_g1,
    validate_g2,
    validate_g3,
    validate_g4,
    validate_g5,
    validate_g6,
    validate_g7,
    validate_g8,
    validate_g9,
    validate_g10,
    validate_g11,
    validate_g12,
)
from app.core.redis import publish_event

logger = structlog.get_logger(__name__)


# ── Pub/sub helper ───────────────────────────────────────────────────

async def _publish_stage_event(
    pipeline_id: str,
    stage: int,
    status: str,
    detail: str = "",
) -> None:
    """Publish a pipeline stage event via Redis pub/sub."""
    channel = f"pipeline:{pipeline_id}"
    await publish_event(channel, {
        "pipeline_id": pipeline_id,
        "stage": stage,
        "status": status,
        "detail": detail,
        "timestamp": time.time(),
    })


# ── Stage 1: Input Layer ─────────────────────────────────────────────

async def input_layer(state: PipelineState) -> dict[str, Any]:
    """Validate idea spec and inject Layer 2 schema."""
    pipeline_id = state.get("pipeline_id", "")
    await _publish_stage_event(pipeline_id, 1, "running", "validating idea spec")

    gate_results = dict(state.get("gate_results", {}))
    errors = list(state.get("errors", []))

    # G1 — validate idea spec
    g1 = validate_g1(state)
    gate_results["G1"] = g1

    if not g1["passed"]:
        errors.append(f"G1 failed: {g1['reason']}")
        await _publish_stage_event(pipeline_id, 1, "failed", g1["reason"])
        return {
            "current_stage": 1,
            "gate_results": gate_results,
            "errors": errors,
        }

    # Schema injection: enrich idea_spec with Layer 2 schema metadata
    idea_spec = dict(state.get("idea_spec", {}))
    idea_spec["_schema_version"] = "2.0"
    idea_spec["_injected_at"] = time.time()

    await _publish_stage_event(pipeline_id, 1, "completed", "idea spec validated")

    return {
        "current_stage": 1,
        "idea_spec": idea_spec,
        "gate_results": gate_results,
        "errors": errors,
    }


# ── Stage 2: C-Suite Analysis ────────────────────────────────────────

async def _run_single_csuite_agent(
    agent_name: str,
    state: PipelineState,
    ai_router: AIRouter,
) -> tuple[str, dict[str, Any]]:
    """Run a single C-suite agent and return (name, output).

    Wraps the call in try/except so a crash in any single agent
    cannot kill the entire asyncio.gather batch.  On failure the
    agent returns an empty dict — G2 will flag missing fields.
    """
    try:
        run_fn = CSUITE_AGENT_MAP[agent_name]
        output = await run_fn(state, ai_router)
        return agent_name, output
    except Exception as exc:
        logger.error(
            "csuite_agent.wrapper_error",
            agent=agent_name,
            error=str(exc),
        )
        return agent_name, {}


async def csuite_analysis(state: PipelineState) -> dict[str, Any]:
    """Run 8 C-suite analyst agents in parallel via asyncio.gather.

    Then run G3 resolver to detect and auto-resolve conflicts.
    Temperature: 0.7 (analytical, not code generation).
    """
    pipeline_id = state.get("pipeline_id", "")
    await _publish_stage_event(pipeline_id, 2, "running", "8 parallel analysts")

    gate_results = dict(state.get("gate_results", {}))
    errors = list(state.get("errors", []))

    # Create AI router (stub for now — production will use real provider)
    ai_router = create_ai_router(provider="stub")

    # Run all 8 C-Suite agents in parallel
    tasks = [
        _run_single_csuite_agent(name, state, ai_router)
        for name in CSUITE_AGENT_NAMES
    ]
    results = await asyncio.gather(*tasks)

    csuite_outputs: dict[str, dict[str, Any]] = {}
    for agent_name, output in results:
        csuite_outputs[agent_name] = output

    # G2 — validate all 8 outputs present with correct schemas
    g2 = validate_g2({"csuite_outputs": csuite_outputs})  # type: ignore[arg-type]
    gate_results["G2"] = g2
    if not g2["passed"]:
        errors.append(f"G2 failed: {g2['reason']}")
        await _publish_stage_event(pipeline_id, 2, "failed", g2["reason"])
        return {
            "current_stage": 2,
            "csuite_outputs": csuite_outputs,
            "gate_results": gate_results,
            "errors": errors,
        }

    # G3 — run conflict resolver
    g3_resolution = await run_g3_resolver(csuite_outputs)
    g3 = validate_g3(state, g3_resolution=g3_resolution)
    gate_results["G3"] = g3

    logger.info(
        "csuite_analysis.g3_resolved",
        conflicts_found=g3_resolution.get("conflicts_found", 0),
        conflicts_resolved=g3_resolution.get("conflicts_resolved", 0),
    )

    await _publish_stage_event(pipeline_id, 2, "completed", "all 8 analysts done")

    return {
        "current_stage": 2,
        "csuite_outputs": csuite_outputs,
        "gate_results": gate_results,
        "errors": errors,
    }


# ── Stage 3: Synthesis ───────────────────────────────────────────────

async def synthesis(state: PipelineState) -> dict[str, Any]:
    """Synthesizer: merge C-suite outputs into a comprehensive plan.

    Validates G4: coherence_score >= 0.85 across 5 dimensions.
    If G4 fails, retries synthesizer once with adjusted prompt.
    """
    pipeline_id = state.get("pipeline_id", "")
    await _publish_stage_event(pipeline_id, 3, "running", "synthesizing plan")

    gate_results = dict(state.get("gate_results", {}))
    errors = list(state.get("errors", []))

    ai_router = create_ai_router(provider="stub")

    # First attempt
    comprehensive_plan = await run_synthesizer(state, ai_router)

    # G4 — coherence_score >= 0.85
    g4 = validate_g4({"comprehensive_plan": comprehensive_plan})  # type: ignore[arg-type]

    if not g4["passed"]:
        # Retry once with adjusted guidance
        logger.warning(
            "synthesis.g4_retry",
            first_score=comprehensive_plan.get("coherence_score", 0),
            reason=g4["reason"],
        )
        await _publish_stage_event(
            pipeline_id, 3, "running", "G4 retry — adjusting synthesis"
        )
        comprehensive_plan = await run_synthesizer(state, ai_router)
        g4 = validate_g4({"comprehensive_plan": comprehensive_plan})  # type: ignore[arg-type]

    gate_results["G4"] = g4

    if not g4["passed"]:
        errors.append(f"G4 failed: {g4['reason']}")
        await _publish_stage_event(pipeline_id, 3, "failed", g4["reason"])
        return {
            "current_stage": 3,
            "comprehensive_plan": comprehensive_plan,
            "gate_results": gate_results,
            "errors": errors,
        }

    await _publish_stage_event(pipeline_id, 3, "completed", "plan synthesised")

    return {
        "current_stage": 3,
        "comprehensive_plan": comprehensive_plan,
        "gate_results": gate_results,
        "errors": errors,
    }


# ── Stage 4: Spec Layer ──────────────────────────────────────────────

_SPEC_AGENTS = (
    "api_spec", "db_spec", "ui_spec", "infra_spec", "test_spec",
)


async def _run_spec_agent(
    agent_name: str,
    plan: dict[str, Any],
) -> tuple[str, dict[str, Any]]:
    """Stub: run a single spec agent."""
    await asyncio.sleep(0)
    return agent_name, {
        "agent": agent_name,
        "spec": f"{agent_name} specification based on plan",
        "schemas": [f"{agent_name}_schema_1"],
    }


async def spec_layer(state: PipelineState) -> dict[str, Any]:
    """Run 5 spec agents in parallel."""
    pipeline_id = state.get("pipeline_id", "")
    await _publish_stage_event(pipeline_id, 4, "running", "5 parallel spec agents")

    plan = state.get("comprehensive_plan", {})
    gate_results = dict(state.get("gate_results", {}))
    errors = list(state.get("errors", []))

    tasks = [_run_spec_agent(name, plan) for name in _SPEC_AGENTS]
    results = await asyncio.gather(*tasks)

    spec_outputs: dict[str, dict[str, Any]] = {}
    for agent_name, output in results:
        spec_outputs[agent_name] = output

    # G5 — all 5 spec outputs present
    g5 = validate_g5({"spec_outputs": spec_outputs})  # type: ignore[arg-type]
    gate_results["G5"] = g5
    if not g5["passed"]:
        errors.append(f"G5 failed: {g5['reason']}")
        await _publish_stage_event(pipeline_id, 4, "failed", g5["reason"])
        return {
            "current_stage": 4,
            "spec_outputs": spec_outputs,
            "gate_results": gate_results,
            "errors": errors,
        }

    await _publish_stage_event(pipeline_id, 4, "completed", "all 5 specs done")

    return {
        "current_stage": 4,
        "spec_outputs": spec_outputs,
        "gate_results": gate_results,
        "errors": errors,
    }


# ── Stage 5: Bootstrap ───────────────────────────────────────────────

async def bootstrap(state: PipelineState) -> dict[str, Any]:
    """Generate BuildManifest and check build cache."""
    pipeline_id = state.get("pipeline_id", "")
    await _publish_stage_event(pipeline_id, 5, "running", "generating build manifest")

    gate_results = dict(state.get("gate_results", {}))
    errors = list(state.get("errors", []))

    # Stub: generate build manifest from spec outputs
    # File paths match what the stub build agents generate
    build_manifest: dict[str, Any] = {
        "files": [
            f"src/{agent}/index.tsx"
            for agent in (
                "prd", "design_system", "layout", "component", "page",
                "api", "state", "integration", "config", "quality",
            )
        ],
        "framework": "react_vite",
        "total_agents": 10,
        "cache_hit": False,  # Stub: always cache miss
    }

    # G6 — manifest has files
    g6 = validate_g6({"build_manifest": build_manifest})  # type: ignore[arg-type]
    gate_results["G6"] = g6
    if not g6["passed"]:
        errors.append(f"G6 failed: {g6['reason']}")
        await _publish_stage_event(pipeline_id, 5, "failed", g6["reason"])
        return {
            "current_stage": 5,
            "build_manifest": build_manifest,
            "gate_results": gate_results,
            "errors": errors,
        }

    await _publish_stage_event(pipeline_id, 5, "completed", "manifest ready")

    return {
        "current_stage": 5,
        "build_manifest": build_manifest,
        "gate_results": gate_results,
        "errors": errors,
    }


# ── Stage 6: Build ───────────────────────────────────────────────────

_BUILD_AGENTS = (
    "prd", "design_system", "layout", "component", "page",
    "api", "state", "integration", "config", "quality",
)


async def _run_build_agent(
    agent_name: str,
    manifest: dict[str, Any],
    plan: dict[str, Any],
) -> tuple[str, dict[str, str]]:
    """Stub: run a single build agent.

    Architecture rule #4: temperature=0, fixed seed for determinism.
    Architecture rule #6: schema injection before each agent.
    """
    await asyncio.sleep(0)
    # Each agent "generates" one file
    file_path = f"src/{agent_name}/index.tsx"
    file_content = (
        f"// Generated by {agent_name} agent\n"
        f"// Plan: {plan.get('title', plan.get('executive_summary', 'untitled')[:40])}\n"
        f"export default function {agent_name.title().replace('_', '')}() "
        "{ return null; }\n"
    )
    return agent_name, {file_path: file_content}


async def build(state: PipelineState) -> dict[str, Any]:
    """Run 10 build agents sequentially with G7 per agent."""
    pipeline_id = state.get("pipeline_id", "")
    await _publish_stage_event(pipeline_id, 6, "running", "10 sequential build agents")

    manifest = state.get("build_manifest", {})
    plan = state.get("comprehensive_plan", {})
    gate_results = dict(state.get("gate_results", {}))
    errors = list(state.get("errors", []))
    generated_files: dict[str, str] = dict(state.get("generated_files", {}))

    for agent_name in _BUILD_AGENTS:
        await _publish_stage_event(
            pipeline_id, 6, "running", f"agent: {agent_name}"
        )

        # Architecture rule #6: schema injection before each agent
        # (stub — in production this injects relevant schemas)

        _name, files = await _run_build_agent(agent_name, manifest, plan)
        generated_files.update(files)

        # G7 — per-agent validation
        check_state: PipelineState = {
            "generated_files": generated_files,
            "errors": errors,
        }
        g7 = validate_g7(check_state, agent_name=agent_name)
        gate_results[f"G7_{agent_name}"] = g7

        if not g7["passed"]:
            errors.append(f"G7 failed for {agent_name}: {g7['reason']}")
            await _publish_stage_event(
                pipeline_id, 6, "failed", f"agent {agent_name} failed G7"
            )
            return {
                "current_stage": 6,
                "generated_files": generated_files,
                "gate_results": gate_results,
                "errors": errors,
            }

    # Architecture rule #5: coherence engine runs AFTER all 10 build agents
    final_state: PipelineState = {
        "generated_files": generated_files,
        "errors": errors,
        "gate_results": gate_results,
        "build_manifest": manifest,
    }

    # G8 — minimum file count
    g8 = validate_g8(final_state)
    gate_results["G8"] = g8

    # G9 — no remaining errors
    g9 = validate_g9(final_state)
    gate_results["G9"] = g9

    # G10 — file coherence (post all agents)
    g10 = validate_g10(final_state)
    gate_results["G10"] = g10

    # G11 — manifest ↔ generated files match
    g11 = validate_g11(final_state)
    gate_results["G11"] = g11

    # G12 — final pipeline validation
    final_state["gate_results"] = gate_results
    g12 = validate_g12(final_state)
    gate_results["G12"] = g12

    if g12["passed"]:
        await _publish_stage_event(pipeline_id, 6, "completed", "build complete")
    else:
        errors.append(f"G12 failed: {g12['reason']}")
        await _publish_stage_event(pipeline_id, 6, "failed", g12["reason"])

    return {
        "current_stage": 6,
        "generated_files": generated_files,
        "gate_results": gate_results,
        "errors": errors,
    }


# ── Error handler ────────────────────────────────────────────────────

async def error_handler(state: PipelineState) -> dict[str, Any]:
    """Terminal node — publishes error event and returns final state."""
    pipeline_id = state.get("pipeline_id", "")
    errors = state.get("errors", [])
    stage = state.get("current_stage", 0)

    await _publish_stage_event(
        pipeline_id, stage, "error",
        f"pipeline failed with {len(errors)} error(s)",
    )

    return {"current_stage": stage, "errors": errors}


# ── Routing functions ────────────────────────────────────────────────

def _after_input(state: PipelineState) -> str:
    """Route after input_layer: if G1 failed → error, else → csuite."""
    gate_results = state.get("gate_results", {})
    g1 = gate_results.get("G1", {})
    if not g1.get("passed", False):
        return "error_handler"
    return "csuite_analysis"


def _after_csuite(state: PipelineState) -> str:
    gate_results = state.get("gate_results", {})
    g2 = gate_results.get("G2", {})
    if not g2.get("passed", False):
        return "error_handler"
    return "synthesis"


def _after_synthesis(state: PipelineState) -> str:
    gate_results = state.get("gate_results", {})
    g4 = gate_results.get("G4", {})
    if not g4.get("passed", False):
        return "error_handler"
    return "spec_layer"


def _after_spec(state: PipelineState) -> str:
    gate_results = state.get("gate_results", {})
    g5 = gate_results.get("G5", {})
    if not g5.get("passed", False):
        return "error_handler"
    return "bootstrap"


def _after_bootstrap(state: PipelineState) -> str:
    gate_results = state.get("gate_results", {})
    g6 = gate_results.get("G6", {})
    if not g6.get("passed", False):
        return "error_handler"
    return "build"


def _after_build(state: PipelineState) -> str:
    gate_results = state.get("gate_results", {})
    g12 = gate_results.get("G12", {})
    if not g12.get("passed", False):
        return "error_handler"
    return END


# ── Graph assembly ───────────────────────────────────────────────────

def build_pipeline_graph() -> StateGraph:
    """Construct and return the (uncompiled) 6-stage pipeline graph."""
    graph = StateGraph(PipelineState)

    # Add nodes
    graph.add_node("input_layer", input_layer)
    graph.add_node("csuite_analysis", csuite_analysis)
    graph.add_node("synthesis", synthesis)
    graph.add_node("spec_layer", spec_layer)
    graph.add_node("bootstrap", bootstrap)
    graph.add_node("build", build)
    graph.add_node("error_handler", error_handler)

    # Entry point
    graph.set_entry_point("input_layer")

    # Conditional edges
    graph.add_conditional_edges("input_layer", _after_input)
    graph.add_conditional_edges("csuite_analysis", _after_csuite)
    graph.add_conditional_edges("synthesis", _after_synthesis)
    graph.add_conditional_edges("spec_layer", _after_spec)
    graph.add_conditional_edges("bootstrap", _after_bootstrap)
    graph.add_conditional_edges("build", _after_build)

    # error_handler → END
    graph.add_edge("error_handler", END)

    return graph


# Alias for convenience
build_graph = build_pipeline_graph

# Compiled graph — ready to invoke
pipeline_graph = build_pipeline_graph().compile()

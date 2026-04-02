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
import os
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
from app.reliability.layer1_pregeneration import (
    generate_env_contract,
    resolve_dependencies,
)
from app.reliability.layer2_schema_driven import (
    generate_openapi_spec,
    generate_pydantic_schemas,
    generate_typescript_types,
    generate_zod_schemas,
)



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
    """Validate idea spec, run Layer 1 contracts, inject Layer 2 schema."""
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

    # ── Layer 1: Pre-generation contracts ─────────────────────────
    # Resolve dependencies from tech stack
    framework = str(idea_spec.get("framework", "react_vite"))
    tech_stack = [framework]
    features = idea_spec.get("features", [])
    if isinstance(features, list):
        tech_stack.extend(str(f) for f in features if isinstance(f, str))

    resolved_deps = resolve_dependencies(tech_stack)

    # Generate env contract
    integrations: list[str] = []
    for feat in (features if isinstance(features, list) else []):
        feat_lower = str(feat).lower()
        for integration in ("stripe", "supabase", "firebase", "openai", "sendgrid", "auth0", "redis"):
            if integration in feat_lower:
                integrations.append(integration)
    env_contract = generate_env_contract(tech_stack, integrations)

    logger.info(
        "input_layer.layer1_complete",
        packages_resolved=len(resolved_deps.packages),
        conflicts_resolved=resolved_deps.conflicts_resolved,
        env_required=len(env_contract.required),
    )

    await _publish_stage_event(pipeline_id, 1, "completed", "idea spec validated + Layer 1 contracts")

    return {
        "current_stage": 1,
        "idea_spec": idea_spec,
        "gate_results": gate_results,
        "errors": errors,
        "resolved_dependencies": resolved_deps.model_dump(),
        "env_contract": env_contract.model_dump(),
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
    """Run 5 spec agents in parallel, then generate Layer 2 schemas."""
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

    # ── Layer 2: Generate schemas from spec outputs ──────────────
    injected_schemas: dict[str, str] = dict(state.get("injected_schemas", {}))

    # OpenAPI spec from api_spec
    openapi_spec = generate_openapi_spec(spec_outputs)
    injected_schemas["openapi_spec"] = openapi_spec

    # Zod schemas from PRD (comprehensive plan contains entity data)
    zod_schemas = generate_zod_schemas(plan)
    injected_schemas["zod_schemas"] = zod_schemas

    # Pydantic schemas from PRD
    pydantic_schemas = generate_pydantic_schemas(plan)
    injected_schemas["pydantic_schemas"] = pydantic_schemas

    # DB types from db_spec SQL output — generated here so they're
    # available BEFORE PageAgent and ComponentAgent in Stage 6
    db_spec = spec_outputs.get("db_spec", {})
    db_sql = db_spec.get("sql", db_spec.get("schema", ""))
    if isinstance(db_sql, str) and ("CREATE TABLE" in db_sql or "CREATE TYPE" in db_sql):
        db_types = generate_typescript_types(db_sql)
        injected_schemas["db_types"] = db_types
        logger.info(
            "spec_layer.db_types_generated",
            length=len(db_types),
        )

    logger.info(
        "spec_layer.layer2_schemas_generated",
        openapi_length=len(openapi_spec),
        zod_length=len(zod_schemas),
        pydantic_length=len(pydantic_schemas),
    )

    await _publish_stage_event(pipeline_id, 4, "completed", "all 5 specs done + Layer 2 schemas")

    return {
        "current_stage": 4,
        "spec_outputs": spec_outputs,
        "gate_results": gate_results,
        "errors": errors,
        "injected_schemas": injected_schemas,
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

from app.agents.build import (
    BUILD_AGENT_MAP,
    BUILD_AGENT_NAMES,
    ContextWindowManager,
    HotfixResult,
    ReviewResult,
    SnapshotService,
    run_hotfix_agent,
    run_review_agent,
)
from app.reliability.layer7_simulation import WiremockManager

# Schema injection map: which Layer 2 schemas each agent receives
_SCHEMA_INJECTION_MAP: dict[str, list[str]] = {
    "scaffold": [],
    "router": [],
    "component": ["zod_schemas", "db_types"],
    "page": ["zod_schemas", "db_types"],
    "api": ["openapi_spec", "pydantic_schemas"],
    "db": ["pydantic_schemas"],
    "auth": [],
    "style": [],
    "test": ["openapi_spec", "zod_schemas", "db_types"],
}


# Known external integrations detected from spec/feature keywords
_INTEGRATION_KEYWORDS: dict[str, str] = {
    "stripe": "stripe",
    "payment": "stripe",
    "supabase": "supabase",
    "resend": "resend",
    "email": "resend",
    "openai": "openai",
    "gpt": "openai",
    "chatgpt": "openai",
    "anthropic": "anthropic",
    "claude": "anthropic",
    "twilio": "twilio",
    "sms": "twilio",
}


def _detect_services(state: PipelineState) -> list[str]:
    """Detect which external services the app needs from spec_outputs + idea_spec."""
    services: set[str] = set()

    # Scan idea_spec features
    idea_spec = state.get("idea_spec", {})
    features = idea_spec.get("features", [])
    if isinstance(features, list):
        for feat in features:
            feat_lower = str(feat).lower()
            for keyword, svc in _INTEGRATION_KEYWORDS.items():
                if keyword in feat_lower:
                    services.add(svc)

    # Scan spec_outputs for integration references
    spec_outputs = state.get("spec_outputs", {})
    for _spec_name, spec_data in (spec_outputs.items() if isinstance(spec_outputs, dict) else []):
        spec_str = str(spec_data).lower()
        for keyword, svc in _INTEGRATION_KEYWORDS.items():
            if keyword in spec_str:
                services.add(svc)

    return sorted(services)


async def build(state: PipelineState) -> dict[str, Any]:
    """Run 10 build agents sequentially with G7 per agent.

    Architecture rules enforced:
      #4: temperature=0, fixed seed (handled by ContextWindowManager)
      #5: coherence engine runs AFTER all 10 build agents (in review_agent)
      #6: schema injection happens BEFORE each relevant agent starts
      #7: Layer 7 — Wiremock intercepts all external API calls

    After each agent:
      1. Capture snapshot via SnapshotService
      2. Validate Gate G7
      3. If G7 fails: call hotfix_agent (Layer 9), retry once
    After agent 9: run review_agent (agent 10)
    Store all generated files in Cloudflare R2.
    """
    pipeline_id = state.get("pipeline_id", "")
    build_id = state.get("build_id", pipeline_id)
    project_id = state.get("project_id", "")
    await _publish_stage_event(pipeline_id, 6, "running", "10 sequential build agents")

    manifest = state.get("build_manifest", {})
    plan = state.get("comprehensive_plan", {})
    gate_results = dict(state.get("gate_results", {}))
    errors = list(state.get("errors", []))
    generated_files: dict[str, str] = dict(state.get("generated_files", {}))
    injected_schemas: dict[str, str] = dict(state.get("injected_schemas", {}))
    snapshot_urls: list[str] = list(state.get("snapshot_urls", []))

    # Create utilities
    ai_router = create_ai_router(provider="stub")
    cwm = ContextWindowManager(ai_router)
    snapshot_service = SnapshotService()

    # ── Layer 7: Wiremock simulation ─────────────────────────────
    detected_services = _detect_services(state)
    wiremock: WiremockManager | None = None
    wiremock_config: dict[str, object] = {"active": False, "services": []}

    if detected_services:
        try:
            wiremock = WiremockManager(mode="inprocess")
            await wiremock.start()
            stubs_registered = await wiremock.configure_stubs(detected_services)
            os.environ["EXTERNAL_API_BASE_URL"] = wiremock.base_url
            wiremock_config = {
                "active": True,
                "base_url": wiremock.base_url,
                "port": wiremock.port,
                "services": detected_services,
                "stubs_registered": stubs_registered,
            }
            logger.info(
                "build.layer7_wiremock_started",
                services=detected_services,
                stubs=stubs_registered,
                base_url=wiremock.base_url,
            )
        except Exception as exc:
            logger.error("build.layer7_wiremock_failed", error=str(exc))
            errors.append(f"Layer 7 Wiremock start failed: {str(exc)[:200]}")

    # ── Run agents 1-9 sequentially ──────────────────────────────
    # Wrapped in try/finally to GUARANTEE Wiremock cleanup even if
    # the pipeline crashes mid-agent or takes an early return on
    # G7 failure. Without this, in-process server threads leak.
    try:
        for idx, agent_name in enumerate(BUILD_AGENT_NAMES, start=1):
            await _publish_stage_event(
                pipeline_id, 6, "running", f"agent {idx}/10: {agent_name}"
            )

            # Architecture rule #6: schema injection before each agent
            agent_schemas = _SCHEMA_INJECTION_MAP.get(agent_name, [])
            for schema_key in agent_schemas:
                if schema_key in injected_schemas:
                    logger.info(
                        "build.schema_injected",
                        agent=agent_name,
                        schema=schema_key,
                        length=len(injected_schemas[schema_key]),
                    )

            # Run the agent
            try:
                run_fn = BUILD_AGENT_MAP[agent_name]
                # Pass current generated_files in state so test_agent can see them
                agent_state: PipelineState = {
                    **state,
                    "generated_files": generated_files,
                    "injected_schemas": injected_schemas,
                }
                agent_files: dict[str, str] = await run_fn(
                    agent_state, ai_router, cwm
                )
                generated_files.update(agent_files)
            except Exception as exc:
                logger.error(
                    "build.agent_error",
                    agent=agent_name,
                    error=str(exc),
                )
                errors.append(f"Agent {agent_name} crashed: {str(exc)[:200]}")

            # Capture snapshot after each agent
            snapshot_url = await snapshot_service.capture_snapshot(
                build_id=str(build_id),
                project_id=str(project_id),
                agent_name=agent_name,
                snapshot_index=idx,
                generated_files=generated_files,
                gate_results=gate_results,
            )
            if snapshot_url:
                snapshot_urls.append(snapshot_url)

            # G7 — per-agent validation
            check_state: PipelineState = {
                "generated_files": generated_files,
                "errors": errors,
            }
            g7 = validate_g7(check_state, agent_name=agent_name)
            gate_results[f"G7_{agent_name}"] = g7

            if not g7["passed"]:
                # Hotfix attempt (Layer 9)
                logger.warning(
                    "build.g7_failed_attempting_hotfix",
                    agent=agent_name,
                    reason=g7["reason"],
                )
                await _publish_stage_event(
                    pipeline_id, 6, "running",
                    f"G7 failed for {agent_name} — attempting hotfix",
                )

                hotfix_state: PipelineState = {
                    **state,
                    "generated_files": generated_files,
                }
                hotfix_result = await run_hotfix_agent(
                    state=hotfix_state,
                    ai_router=ai_router,
                    context_window_manager=cwm,
                    failed_agent=agent_name,
                    error_details=g7["reason"],
                    generated_files=generated_files,
                )

                if hotfix_result.success:
                    # Re-validate after hotfix
                    g7_retry = validate_g7(check_state, agent_name=agent_name)
                    gate_results[f"G7_{agent_name}"] = g7_retry
                    if g7_retry["passed"]:
                        logger.info("build.hotfix_succeeded", agent=agent_name)
                        continue

                # Hotfix failed or didn't resolve — pipeline fails
                errors.append(f"G7 failed for {agent_name}: {g7['reason']}")
                await _publish_stage_event(
                    pipeline_id, 6, "failed",
                    f"agent {agent_name} failed G7 (hotfix unsuccessful)",
                )
                return {
                    "current_stage": 6,
                    "generated_files": generated_files,
                    "gate_results": gate_results,
                    "errors": errors,
                    "injected_schemas": injected_schemas,
                    "snapshot_urls": snapshot_urls,
                    "wiremock_config": wiremock_config,
                }

        # ── G8/G9 pre-checks before review_agent ─────────────────────
        final_state: PipelineState = {
            "generated_files": generated_files,
            "errors": errors,
            "gate_results": gate_results,
            "build_manifest": manifest,
        }

        g8 = validate_g8(final_state)
        gate_results["G8"] = g8
        g9 = validate_g9(final_state)
        gate_results["G9"] = g9

        await _publish_stage_event(pipeline_id, 6, "completed", "all 10 agents done")

        return {
            "current_stage": 6,
            "generated_files": generated_files,
            "gate_results": gate_results,
            "errors": errors,
            "injected_schemas": injected_schemas,
            "snapshot_urls": snapshot_urls,
            "build_id": build_id,
            "wiremock_config": wiremock_config,
        }
    finally:
        # GUARANTEED cleanup: verify + stop Wiremock and remove env var
        # even on crash, early return, or unexpected exception.
        if wiremock is not None and wiremock.is_running:
            try:
                # Verify all calls matched stubs before shutdown
                verification = await wiremock.verify_all_calls()
                if not verification.verified:
                    unmatched_summary = ", ".join(
                        f"{r.method} {r.url}"
                        for r in verification.unmatched_requests[:5]
                    )
                    logger.warning(
                        "build.layer7_unmatched_requests",
                        unmatched=len(verification.unmatched_requests),
                        summary=unmatched_summary,
                    )
                await wiremock.stop()
                logger.info("build.layer7_wiremock_stopped_finally")
            except Exception as exc:
                logger.error(
                    "build.layer7_wiremock_stop_error", error=str(exc)
                )
        os.environ.pop("EXTERNAL_API_BASE_URL", None)


# ── Review Agent ─────────────────────────────────────────────────────

async def review_agent_node(state: PipelineState) -> dict[str, Any]:
    """Review agent graph node — delegates to the real review agent.

    Architecture rule #5: File coherence engine runs ONLY here,
    never from individual build agents.

    The real review_agent (Agent 10) handles:
      - Layer 4 coherence + hotfix attempt
      - G8 build verification (tsc, eslint, build, smoke)
      - G11 SAST security scan (Semgrep, Bandit)
      - G12 visual regression (Playwright)
      - Layer 8 post-build checks (Lighthouse, axe, dead code, seeds)
      - Final snapshot capture

    Layer 7: After review, verify Wiremock calls and shut down.
    """
    pipeline_id = state.get("pipeline_id", "")
    await _publish_stage_event(
        pipeline_id, 6, "running", "review agent — full validation"
    )

    gate_results = dict(state.get("gate_results", {}))
    errors = list(state.get("errors", []))
    generated_files: dict[str, str] = dict(state.get("generated_files", {}))
    manifest = state.get("build_manifest", {})

    # Run the real review agent
    ai_router = create_ai_router(provider="stub")
    cwm = ContextWindowManager(ai_router)

    review_result = await run_review_agent(state, ai_router, cwm)
    review_dict = review_result.model_dump()

    # Extract coherence report from review
    coherence_dict = review_result.coherence_report

    logger.info(
        "review_agent_node.complete",
        build_status=review_result.build_status,
        all_passed=review_result.all_passed,
        steps=len(review_result.steps),
    )

    # Layer 7 Wiremock verification and cleanup is handled by the
    # try/finally block in build() — no action needed here.

    # Map review results to gate results
    review_state: PipelineState = {
        "generated_files": generated_files,
        "errors": errors,
        "gate_results": gate_results,
        "build_manifest": manifest,
        "coherence_report": coherence_dict,
    }

    # G10 — file coherence
    g10 = validate_g10(review_state)
    gate_results["G10"] = g10
    if not g10["passed"]:
        errors.append(f"G10 coherence failed: {g10['reason']}")

    # G11 — manifest ↔ generated files match
    g11 = validate_g11(review_state)
    gate_results["G11"] = g11

    # G12 — final pipeline validation
    review_state["gate_results"] = gate_results
    g12 = validate_g12(review_state)
    gate_results["G12"] = g12

    if g12["passed"] and review_result.all_passed:
        await _publish_stage_event(pipeline_id, 6, "completed", "review passed — build COMPLETED")
    else:
        if not g12["passed"]:
            errors.append(f"G12 failed: {g12['reason']}")
        await _publish_stage_event(pipeline_id, 6, "failed", review_result.build_status)

    return {
        "current_stage": 6,
        "generated_files": generated_files,
        "gate_results": gate_results,
        "errors": errors,
        "coherence_report": coherence_dict,
        "review_result": review_dict,
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
    """Route after build: if G8/G9 failed → error, else → review_agent."""
    gate_results = state.get("gate_results", {})
    g8 = gate_results.get("G8", {})
    g9 = gate_results.get("G9", {})
    if not g8.get("passed", True) or not g9.get("passed", True):
        return "error_handler"
    return "review_agent"


def _after_review(state: PipelineState) -> str:
    """Route after review_agent: if G12 failed → error, else → END."""
    gate_results = state.get("gate_results", {})
    g12 = gate_results.get("G12", {})
    if not g12.get("passed", False):
        return "error_handler"
    return END


# ── Graph assembly ───────────────────────────────────────────────────

def build_pipeline_graph() -> StateGraph:
    """Construct and return the (uncompiled) 6-stage pipeline graph.

    Architecture:
      input_layer → csuite_analysis → synthesis → spec_layer
      → bootstrap → build → review_agent → END

    review_agent is a separate node (not part of build) to enforce
    rule #5: coherence engine ONLY runs after all 10 build agents.
    """
    graph = StateGraph(PipelineState)

    # Add nodes
    graph.add_node("input_layer", input_layer)
    graph.add_node("csuite_analysis", csuite_analysis)
    graph.add_node("synthesis", synthesis)
    graph.add_node("spec_layer", spec_layer)
    graph.add_node("bootstrap", bootstrap)
    graph.add_node("build", build)
    graph.add_node("review_agent", review_agent_node)
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
    graph.add_conditional_edges("review_agent", _after_review)

    # error_handler → END
    graph.add_edge("error_handler", END)

    return graph


# Alias for convenience
build_graph = build_pipeline_graph

# Compiled graph — ready to invoke
pipeline_graph = build_pipeline_graph().compile()

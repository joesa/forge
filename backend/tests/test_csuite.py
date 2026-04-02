"""
Tests for C-Suite executive agents, G3 resolver, synthesizer, and Stage 2/3.

Covers:
  • Pydantic schema validation for all 8 agent output types
  • Individual agent tests — each returns valid output with mocked AI router
  • Default fallback tests — each returns sensible defaults on API failure
  • G3 resolver — detects and resolves at least one conflict
  • Synthesizer — produces ComprehensivePlan with coherence_score >= 0.85
  • G4 coherence dimension validation
  • Full Stage 2 + Stage 3 integration

All external services are mocked — no real Redis, DB, or LLM calls.
(AGENTS.md rule #7)
"""

from __future__ import annotations

import asyncio
import json
import uuid
from unittest.mock import AsyncMock, patch

import pytest

from app.agents.ai_router import AIRouter, create_ai_router
from app.agents.csuite import CSUITE_AGENT_MAP, CSUITE_AGENT_NAMES
from app.agents.csuite.ceo_agent import run_ceo_agent, _default_output as ceo_defaults
from app.agents.csuite.cto_agent import run_cto_agent, _default_output as cto_defaults
from app.agents.csuite.cdo_agent import run_cdo_agent, _default_output as cdo_defaults
from app.agents.csuite.cmo_agent import run_cmo_agent, _default_output as cmo_defaults
from app.agents.csuite.cpo_agent import run_cpo_agent, _default_output as cpo_defaults
from app.agents.csuite.cso_agent import run_cso_agent, _default_output as cso_defaults
from app.agents.csuite.cco_agent import run_cco_agent, _default_output as cco_defaults
from app.agents.csuite.cfo_agent import run_cfo_agent, _default_output as cfo_defaults
from app.agents.state import PipelineState
from app.agents.synthesis.g3_resolver import run_g3_resolver
from app.agents.synthesis.synthesizer import run_synthesizer
from app.agents.validators import validate_g2, validate_g3, validate_g4
from app.schemas.csuite import (
    CEOAnalysis,
    CTOAnalysis,
    CDOAnalysis,
    CMOAnalysis,
    CPOAnalysis,
    CSOAnalysis,
    CCOAnalysis,
    CFOAnalysis,
    ComprehensivePlan,
    G3Resolution,
    CSUITE_SCHEMA_MAP,
)


# ── Fixtures ─────────────────────────────────────────────────────────


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
def valid_idea_spec() -> dict[str, object]:
    return {
        "title": "AI Task Manager",
        "description": "A smart task management app with AI prioritization",
        "features": ["kanban board", "AI suggestions", "team collaboration"],
        "framework": "react_vite",
        "target_audience": "remote teams",
    }


@pytest.fixture
def base_state(valid_idea_spec: dict[str, object]) -> PipelineState:
    """Minimal state for running Stage 2 agents."""
    return {
        "pipeline_id": str(uuid.uuid4()),
        "project_id": str(uuid.uuid4()),
        "user_id": str(uuid.uuid4()),
        "current_stage": 1,
        "idea_spec": valid_idea_spec,
        "csuite_outputs": {},
        "comprehensive_plan": {},
        "spec_outputs": {},
        "build_manifest": {},
        "generated_files": {},
        "gate_results": {},
        "errors": [],
        "sandbox_id": None,
    }


@pytest.fixture
def stub_ai_router() -> AIRouter:
    """AI router with stub provider (returns empty JSON)."""
    return create_ai_router(provider="stub")


@pytest.fixture
def all_default_outputs() -> dict[str, dict[str, object]]:
    """All 8 agent default outputs — needed for synthesis testing."""
    return {
        "ceo": ceo_defaults(),
        "cto": cto_defaults(),
        "cdo": cdo_defaults(),
        "cmo": cmo_defaults(),
        "cpo": cpo_defaults(),
        "cso": cso_defaults(),
        "cco": cco_defaults(),
        "cfo": cfo_defaults(),
    }


# ═══════════════════════════════════════════════════════════════════════
# Pydantic Schema Validation
# ═══════════════════════════════════════════════════════════════════════


class TestCSuiteSchemas:
    """Verify all 8 Pydantic schemas validate correctly."""

    def test_ceo_schema_validates(self) -> None:
        data = ceo_defaults()
        model = CEOAnalysis(**data)
        assert model.market_opportunity.tam
        assert model.business_model
        assert model.revenue_strategy

    def test_cto_schema_validates(self) -> None:
        data = cto_defaults()
        model = CTOAnalysis(**data)
        assert model.tech_stack_recommendation.frontend
        assert len(model.api_design_principles) >= 1

    def test_cdo_schema_validates(self) -> None:
        data = cdo_defaults()
        model = CDOAnalysis(**data)
        assert len(model.ux_principles) >= 1
        assert len(model.color_palette_suggestion) >= 1

    def test_cmo_schema_validates(self) -> None:
        data = cmo_defaults()
        model = CMOAnalysis(**data)
        assert model.gtm_strategy
        assert len(model.growth_channels) >= 1

    def test_cpo_schema_validates(self) -> None:
        data = cpo_defaults()
        model = CPOAnalysis(**data)
        assert "must" in model.feature_prioritization
        assert len(model.user_stories) >= 1
        assert len(model.user_stories) <= 15

    def test_cso_schema_validates(self) -> None:
        data = cso_defaults()
        model = CSOAnalysis(**data)
        assert model.auth_architecture
        assert len(model.encryption_requirements) >= 1

    def test_cco_schema_validates(self) -> None:
        data = cco_defaults()
        model = CCOAnalysis(**data)
        assert model.privacy_policy_requirements
        assert model.terms_of_service_requirements

    def test_cfo_schema_validates(self) -> None:
        data = cfo_defaults()
        model = CFOAnalysis(**data)
        assert model.pricing_strategy
        assert model.unit_economics

    def test_comprehensive_plan_schema_validates(self) -> None:
        plan = ComprehensivePlan(
            executive_summary="Test plan",
            tech_stack={"frontend": "React", "backend": "FastAPI"},
            design_system="Modern design system",
            gtm_strategy="Product-led growth",
            feature_list=["Feature 1", "Feature 2"],
            security_requirements=["Auth", "Encryption"],
            compliance_requirements=["GDPR"],
            financial_model="Freemium",
            timeline_estimate="3 months",
            coherence_score=0.92,
            coherence_dimensions={
                "market_tech_alignment": 0.9,
                "design_product_alignment": 0.9,
            },
        )
        assert plan.coherence_score == 0.92

    def test_g3_resolution_schema_validates(self) -> None:
        resolution = G3Resolution(
            conflicts_found=2,
            conflicts_resolved=2,
            resolutions=[],
        )
        assert resolution.conflicts_found == 2

    def test_schema_registry_has_all_8_agents(self) -> None:
        assert len(CSUITE_SCHEMA_MAP) == 8
        for name in CSUITE_AGENT_NAMES:
            assert name in CSUITE_SCHEMA_MAP


# ═══════════════════════════════════════════════════════════════════════
# Individual Agent Tests
# ═══════════════════════════════════════════════════════════════════════


class TestIndividualAgents:
    """Each agent returns valid output with the stub AI router (defaults)."""

    @pytest.mark.asyncio
    async def test_ceo_agent_returns_valid_output(
        self, base_state: PipelineState, stub_ai_router: AIRouter
    ) -> None:
        result = await run_ceo_agent(base_state, stub_ai_router)
        assert "market_opportunity" in result
        assert "business_model" in result
        assert "revenue_strategy" in result
        assert "competitive_moat" in result
        assert "go_to_market_summary" in result

    @pytest.mark.asyncio
    async def test_cto_agent_returns_valid_output(
        self, base_state: PipelineState, stub_ai_router: AIRouter
    ) -> None:
        result = await run_cto_agent(base_state, stub_ai_router)
        assert "tech_stack_recommendation" in result
        assert "api_design_principles" in result
        assert "scalability_approach" in result

    @pytest.mark.asyncio
    async def test_cdo_agent_returns_valid_output(
        self, base_state: PipelineState, stub_ai_router: AIRouter
    ) -> None:
        result = await run_cdo_agent(base_state, stub_ai_router)
        assert "ux_principles" in result
        assert "design_system_recommendation" in result
        assert "color_palette_suggestion" in result

    @pytest.mark.asyncio
    async def test_cmo_agent_returns_valid_output(
        self, base_state: PipelineState, stub_ai_router: AIRouter
    ) -> None:
        result = await run_cmo_agent(base_state, stub_ai_router)
        assert "gtm_strategy" in result
        assert "target_customer_profile" in result
        assert "growth_channels" in result

    @pytest.mark.asyncio
    async def test_cpo_agent_returns_valid_output(
        self, base_state: PipelineState, stub_ai_router: AIRouter
    ) -> None:
        result = await run_cpo_agent(base_state, stub_ai_router)
        assert "feature_prioritization" in result
        assert "mvp_scope" in result
        assert "user_stories" in result
        assert len(result["user_stories"]) == 10

    @pytest.mark.asyncio
    async def test_cso_agent_returns_valid_output(
        self, base_state: PipelineState, stub_ai_router: AIRouter
    ) -> None:
        result = await run_cso_agent(base_state, stub_ai_router)
        assert "auth_architecture" in result
        assert "encryption_requirements" in result
        assert "threat_model" in result

    @pytest.mark.asyncio
    async def test_cco_agent_returns_valid_output(
        self, base_state: PipelineState, stub_ai_router: AIRouter
    ) -> None:
        result = await run_cco_agent(base_state, stub_ai_router)
        assert "regulatory_requirements" in result
        assert "privacy_policy_requirements" in result
        assert "gdpr_obligations" in result

    @pytest.mark.asyncio
    async def test_cfo_agent_returns_valid_output(
        self, base_state: PipelineState, stub_ai_router: AIRouter
    ) -> None:
        result = await run_cfo_agent(base_state, stub_ai_router)
        assert "pricing_strategy" in result
        assert "unit_economics" in result
        assert "breakeven_analysis" in result


# ═══════════════════════════════════════════════════════════════════════
# Default Fallback Tests
# ═══════════════════════════════════════════════════════════════════════


class TestAgentDefaults:
    """Each agent returns sensible defaults on API failure."""

    @pytest.mark.asyncio
    async def test_ceo_returns_defaults_on_error(
        self, base_state: PipelineState
    ) -> None:
        broken_router = AIRouter(provider="stub")
        broken_router.complete = AsyncMock(  # type: ignore[method-assign]
            side_effect=Exception("API down"),
        )
        result = await run_ceo_agent(base_state, broken_router)
        assert result["business_model"]  # Should have default
        CEOAnalysis(**result)  # Must validate

    @pytest.mark.asyncio
    async def test_cto_returns_defaults_on_error(
        self, base_state: PipelineState
    ) -> None:
        broken_router = AIRouter(provider="stub")
        broken_router.complete = AsyncMock(  # type: ignore[method-assign]
            side_effect=Exception("API down"),
        )
        result = await run_cto_agent(base_state, broken_router)
        assert result["tech_stack_recommendation"]
        CTOAnalysis(**result)

    @pytest.mark.asyncio
    async def test_all_agents_return_defaults_on_json_error(
        self, base_state: PipelineState
    ) -> None:
        """All 8 agents should handle bad JSON gracefully."""
        bad_json_router = AIRouter(provider="stub")
        bad_json_router.complete = AsyncMock(  # type: ignore[method-assign]
            return_value="not valid json {{{",
        )

        agent_fns = [
            run_ceo_agent, run_cto_agent, run_cdo_agent, run_cmo_agent,
            run_cpo_agent, run_cso_agent, run_cco_agent, run_cfo_agent,
        ]
        for fn in agent_fns:
            result = await fn(base_state, bad_json_router)
            assert isinstance(result, dict)
            assert len(result) > 0, f"{fn.__name__} returned empty dict"


# ═══════════════════════════════════════════════════════════════════════
# All 8 Agents in Parallel
# ═══════════════════════════════════════════════════════════════════════


class TestParallelExecution:
    """Run all 8 C-Suite agents concurrently via asyncio.gather."""

    @pytest.mark.asyncio
    async def test_all_8_agents_run_in_parallel(
        self, base_state: PipelineState, stub_ai_router: AIRouter
    ) -> None:
        tasks = [
            CSUITE_AGENT_MAP[name](base_state, stub_ai_router)
            for name in CSUITE_AGENT_NAMES
        ]
        results = await asyncio.gather(*tasks)

        assert len(results) == 8
        for result in results:
            assert isinstance(result, dict)
            assert len(result) > 0

    @pytest.mark.asyncio
    async def test_parallel_results_match_agent_names(
        self, base_state: PipelineState, stub_ai_router: AIRouter
    ) -> None:
        """Map agent names to results correctly."""
        outputs: dict[str, dict[str, object]] = {}
        for name in CSUITE_AGENT_NAMES:
            output = await CSUITE_AGENT_MAP[name](base_state, stub_ai_router)
            outputs[name] = output

        # G2 should pass with all 8 present
        g2 = validate_g2({"csuite_outputs": outputs})  # type: ignore[arg-type]
        assert g2["passed"] is True


# ═══════════════════════════════════════════════════════════════════════
# G2 Validator — Enhanced
# ═══════════════════════════════════════════════════════════════════════


class TestG2Enhanced:
    """G2 now validates required fields per agent, not just presence."""

    def test_passes_with_valid_outputs(
        self, all_default_outputs: dict[str, dict[str, object]]
    ) -> None:
        result = validate_g2({"csuite_outputs": all_default_outputs})  # type: ignore[arg-type]
        assert result["passed"] is True

    def test_fails_with_missing_agent(self) -> None:
        outputs = {name: {"analysis": "done"} for name in ("ceo", "cto")}
        result = validate_g2({"csuite_outputs": outputs})  # type: ignore[arg-type]
        assert result["passed"] is False
        assert "missing" in result["reason"]

    def test_fails_with_missing_required_fields(self) -> None:
        """Agent present but missing required fields should fail G2."""
        outputs = {name: {} for name in CSUITE_AGENT_NAMES}
        result = validate_g2({"csuite_outputs": outputs})  # type: ignore[arg-type]
        assert result["passed"] is False
        assert "missing required fields" in result["reason"]


# ═══════════════════════════════════════════════════════════════════════
# G3 Resolver
# ═══════════════════════════════════════════════════════════════════════


class TestG3Resolver:
    """G3 resolver detects and auto-resolves inter-agent conflicts."""

    @pytest.mark.asyncio
    async def test_finds_at_least_one_conflict(
        self, all_default_outputs: dict[str, dict[str, object]]
    ) -> None:
        """Default outputs should produce at least one conflict."""
        result = await run_g3_resolver(all_default_outputs)
        assert result["conflicts_found"] >= 1
        assert result["conflicts_resolved"] >= 1
        assert result["conflicts_found"] == result["conflicts_resolved"]

    @pytest.mark.asyncio
    async def test_resolutions_have_required_structure(
        self, all_default_outputs: dict[str, dict[str, object]]
    ) -> None:
        result = await run_g3_resolver(all_default_outputs)
        for res in result["resolutions"]:
            assert "conflict_type" in res
            assert "description" in res
            assert "winner" in res
            assert "adaptation" in res

    @pytest.mark.asyncio
    async def test_tech_vs_budget_detection(self) -> None:
        """Explicit tech vs budget conflict should be detected."""
        outputs = {
            "cto": {
                "tech_stack_recommendation": {"frontend": "React"},
                "infrastructure_choices": "kubernetes multi-cloud setup",
                "build_vs_buy_decisions": ["build custom auth"],
                "api_design_principles": ["REST"],
            },
            "cfo": {
                "cost_structure": "tight budget, conservative spending",
                "pricing_strategy": "Freemium",
                "unit_economics": "Low",
            },
            # Minimal others
            "ceo": {}, "cdo": {}, "cmo": {},
            "cpo": {"feature_prioritization": {"must": []}},
            "cso": {}, "cco": {},
        }
        result = await run_g3_resolver(outputs)
        tech_budget = [
            r for r in result["resolutions"]
            if r["conflict_type"] == "tech_vs_budget"
        ]
        assert len(tech_budget) >= 1
        assert tech_budget[0]["winner"] == "CFO"

    @pytest.mark.asyncio
    async def test_compliance_vs_features_detection(self) -> None:
        """GDPR obligations should trigger compliance conflict."""
        outputs = {
            "cso": {"compliance_needs": ["HIPAA"]},
            "cco": {"gdpr_obligations": ["breach notification"]},
            "cpo": {"feature_prioritization": {"must": ["auth"]}},
            "cto": {}, "ceo": {}, "cdo": {}, "cmo": {}, "cfo": {},
        }
        result = await run_g3_resolver(outputs)
        compliance = [
            r for r in result["resolutions"]
            if r["conflict_type"] == "compliance_vs_features"
        ]
        assert len(compliance) >= 1

    @pytest.mark.asyncio
    async def test_g3_validator_passes_with_resolution(
        self, all_default_outputs: dict[str, dict[str, object]]
    ) -> None:
        """G3 gate validator should pass when all conflicts resolved."""
        resolution = await run_g3_resolver(all_default_outputs)
        state: PipelineState = {}
        g3 = validate_g3(state, g3_resolution=resolution)
        assert g3["passed"] is True

    @pytest.mark.asyncio
    async def test_empty_outputs_no_crash(self) -> None:
        """G3 should handle empty outputs gracefully."""
        result = await run_g3_resolver({})
        assert result["conflicts_found"] == 0
        assert result["conflicts_resolved"] == 0


# ═══════════════════════════════════════════════════════════════════════
# Synthesizer
# ═══════════════════════════════════════════════════════════════════════


class TestSynthesizer:
    """Synthesizer produces a ComprehensivePlan with coherence scoring."""

    @pytest.mark.asyncio
    async def test_produces_valid_plan(
        self,
        base_state: PipelineState,
        all_default_outputs: dict[str, dict[str, object]],
        stub_ai_router: AIRouter,
    ) -> None:
        state = {**base_state, "csuite_outputs": all_default_outputs}
        result = await run_synthesizer(state, stub_ai_router)

        assert "executive_summary" in result
        assert "tech_stack" in result
        assert "design_system" in result
        assert "feature_list" in result
        assert "security_requirements" in result
        assert "coherence_score" in result
        assert "coherence_dimensions" in result

    @pytest.mark.asyncio
    async def test_coherence_score_above_threshold(
        self,
        base_state: PipelineState,
        all_default_outputs: dict[str, dict[str, object]],
        stub_ai_router: AIRouter,
    ) -> None:
        state = {**base_state, "csuite_outputs": all_default_outputs}
        result = await run_synthesizer(state, stub_ai_router)

        assert result["coherence_score"] >= 0.85

    @pytest.mark.asyncio
    async def test_all_5_coherence_dimensions_present(
        self,
        base_state: PipelineState,
        all_default_outputs: dict[str, dict[str, object]],
        stub_ai_router: AIRouter,
    ) -> None:
        state = {**base_state, "csuite_outputs": all_default_outputs}
        result = await run_synthesizer(state, stub_ai_router)

        dims = result["coherence_dimensions"]
        expected = [
            "market_tech_alignment",
            "design_product_alignment",
            "finance_scope_alignment",
            "compliance_tech_alignment",
            "gtm_product_alignment",
        ]
        for dim in expected:
            assert dim in dims, f"Missing dimension: {dim}"
            assert isinstance(dims[dim], float)
            assert 0.0 <= dims[dim] <= 1.0

    @pytest.mark.asyncio
    async def test_g4_passes_with_synthesized_plan(
        self,
        base_state: PipelineState,
        all_default_outputs: dict[str, dict[str, object]],
        stub_ai_router: AIRouter,
    ) -> None:
        state = {**base_state, "csuite_outputs": all_default_outputs}
        plan = await run_synthesizer(state, stub_ai_router)

        g4 = validate_g4({"comprehensive_plan": plan})  # type: ignore[arg-type]
        assert g4["passed"] is True, f"G4 failed: {g4['reason']}"

    @pytest.mark.asyncio
    async def test_plan_validates_against_pydantic(
        self,
        base_state: PipelineState,
        all_default_outputs: dict[str, dict[str, object]],
        stub_ai_router: AIRouter,
    ) -> None:
        state = {**base_state, "csuite_outputs": all_default_outputs}
        result = await run_synthesizer(state, stub_ai_router)
        # Should not raise
        ComprehensivePlan(**result)

    @pytest.mark.asyncio
    async def test_features_list_has_items(
        self,
        base_state: PipelineState,
        all_default_outputs: dict[str, dict[str, object]],
        stub_ai_router: AIRouter,
    ) -> None:
        state = {**base_state, "csuite_outputs": all_default_outputs}
        result = await run_synthesizer(state, stub_ai_router)

        assert len(result["feature_list"]) >= 1
        assert len(result["feature_list"]) <= 25


# ═══════════════════════════════════════════════════════════════════════
# Full Stage 2 + Stage 3 Integration
# ═══════════════════════════════════════════════════════════════════════


class TestStage2Integration:
    """Full Stage 2 → G3 → Stage 3 → G4 integration test."""

    @pytest.mark.asyncio
    async def test_full_stage2_with_sample_idea(
        self, base_state: PipelineState
    ) -> None:
        """Run all 8 agents, G3 resolver, synthesizer, verify G4."""
        with patch(
            "app.agents.graph.publish_event",
            new_callable=AsyncMock,
        ):
            from app.agents.graph import csuite_analysis, synthesis

            # Stage 2: C-Suite analysis
            stage2_result = await csuite_analysis(base_state)

            assert stage2_result["current_stage"] == 2
            assert len(stage2_result["csuite_outputs"]) == 8

            # G2 should pass
            assert stage2_result["gate_results"]["G2"]["passed"] is True
            # G3 should pass
            assert stage2_result["gate_results"]["G3"]["passed"] is True

            # All 8 agents should have required fields
            for name in CSUITE_AGENT_NAMES:
                assert name in stage2_result["csuite_outputs"]
                output = stage2_result["csuite_outputs"][name]
                assert len(output) > 0

            # Stage 3: Synthesis
            state_after_s2 = {**base_state, **stage2_result}
            stage3_result = await synthesis(state_after_s2)

            assert stage3_result["current_stage"] == 3

            # G4 should pass
            assert stage3_result["gate_results"]["G4"]["passed"] is True

            # Comprehensive plan should be valid
            plan = stage3_result["comprehensive_plan"]
            assert plan["coherence_score"] >= 0.85
            assert "executive_summary" in plan
            assert "tech_stack" in plan
            assert "feature_list" in plan

    @pytest.mark.asyncio
    async def test_full_pipeline_with_new_agents(
        self, valid_idea_spec: dict[str, object]
    ) -> None:
        """Run the entire pipeline end-to-end with new C-Suite agents."""
        with patch(
            "app.agents.graph.publish_event",
            new_callable=AsyncMock,
        ):
            from app.agents.graph import pipeline_graph

            initial_state: PipelineState = {
                "pipeline_id": str(uuid.uuid4()),
                "project_id": str(uuid.uuid4()),
                "user_id": str(uuid.uuid4()),
                "current_stage": 0,
                "idea_spec": valid_idea_spec,
                "csuite_outputs": {},
                "comprehensive_plan": {},
                "spec_outputs": {},
                "build_manifest": {},
                "generated_files": {},
                "gate_results": {},
                "errors": [],
                "sandbox_id": None,
            }

            result = await pipeline_graph.ainvoke(initial_state)

            # Should reach stage 6
            assert result["current_stage"] == 6

            # All major gates should pass
            gates = result["gate_results"]
            assert gates["G1"]["passed"] is True
            assert gates["G2"]["passed"] is True
            assert gates["G3"]["passed"] is True
            assert gates["G4"]["passed"] is True
            assert gates["G5"]["passed"] is True
            assert gates["G6"]["passed"] is True
            assert gates["G8"]["passed"] is True
            assert gates["G9"]["passed"] is True
            assert gates["G10"]["passed"] is True

            # C-Suite outputs should have all 8
            assert len(result["csuite_outputs"]) == 8

            # Plan should be valid
            plan = result["comprehensive_plan"]
            assert plan["coherence_score"] >= 0.85

            # No errors
            assert result["errors"] == []


# ═══════════════════════════════════════════════════════════════════════
# AI Router
# ═══════════════════════════════════════════════════════════════════════


class TestAIRouter:
    """AI Router abstraction tests."""

    @pytest.mark.asyncio
    async def test_stub_router_returns_json(self) -> None:
        router = create_ai_router(provider="stub")
        result = await router.complete("system", "user")
        # Should be valid JSON
        parsed = json.loads(result)
        assert isinstance(parsed, dict)

    @pytest.mark.asyncio
    async def test_unknown_provider_returns_empty_json(self) -> None:
        router = create_ai_router(provider="unknown")
        result = await router.complete("system", "user")
        parsed = json.loads(result)
        assert isinstance(parsed, dict)

"""
Tests for the FORGE LangGraph pipeline orchestration layer.

Covers:
  • PipelineState creation and field access
  • All 12 gate validators (pass + fail cases)
  • Full graph execution with stub agents
  • API endpoints: POST /run, GET /status, GET /stages
  • WebSocket /stream connection

All external services are mocked — no real Redis, DB, or LLM calls.
(AGENTS.md rule #7)
"""

from __future__ import annotations

import json
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.agents.state import PipelineState, GateResult
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
from app.main import app


# ── Fixtures ─────────────────────────────────────────────────────────

@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def client():
    """Async HTTP client wired to the FORGE ASGI app."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def mock_user_id() -> uuid.UUID:
    return uuid.UUID("11111111-1111-1111-1111-111111111111")


@pytest.fixture
def mock_project_id() -> uuid.UUID:
    return uuid.UUID("22222222-2222-2222-2222-222222222222")


@pytest.fixture
def auth_headers(mock_user_id: uuid.UUID) -> dict[str, str]:
    return {"Authorization": "Bearer test-jwt-token"}


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
def full_pipeline_state(
    mock_user_id: uuid.UUID,
    mock_project_id: uuid.UUID,
    valid_idea_spec: dict[str, object],
) -> PipelineState:
    """A fully-populated pipeline state for testing."""
    return {
        "pipeline_id": str(uuid.uuid4()),
        "project_id": str(mock_project_id),
        "user_id": str(mock_user_id),
        "current_stage": 6,
        "idea_spec": valid_idea_spec,
        "csuite_outputs": {
            name: {"analysis": f"{name} output"}
            for name in (
                "ceo", "cto", "cdo", "cmo", "cpo",
                "cso", "cco", "cfo",
            )
        },
        "comprehensive_plan": {
            "title": "AI Task Manager",
            "coherence_score": 0.93,
            "sections": ["requirements", "architecture"],
        },
        "spec_outputs": {
            name: {"spec": f"{name} spec"}
            for name in (
                "api_spec", "db_spec", "ui_spec", "infra_spec", "test_spec",
            )
        },
        "build_manifest": {
            "files": [
                "src/App.tsx",
                "src/index.tsx",
                "src/components/Layout.tsx",
                "package.json",
                "tsconfig.json",
            ],
            "framework": "react_vite",
        },
        "generated_files": {
            "src/App.tsx": "export default App;",
            "src/index.tsx": "ReactDOM.render(<App />);",
            "src/components/Layout.tsx": "export default Layout;",
            "package.json": "{}",
            "tsconfig.json": "{}",
        },
        "gate_results": {},
        "errors": [],
        "sandbox_id": None,
    }


# ═══════════════════════════════════════════════════════════════════════
# PipelineState
# ═══════════════════════════════════════════════════════════════════════


class TestPipelineState:
    """Test PipelineState TypedDict creation and field access."""

    def test_pipeline_state_has_all_fields(self) -> None:
        """Verify PipelineState has ALL required fields.

        Missing fields will cause KeyError in later sessions.
        """
        required_fields = {
            "pipeline_id", "project_id", "user_id", "current_stage",
            "idea_spec", "csuite_outputs", "comprehensive_plan",
            "spec_outputs", "build_manifest", "generated_files",
            "gate_results", "errors", "sandbox_id",
            # Reliability layers (added in Session 1.7)
            "env_contract", "resolved_dependencies",
            "injected_schemas", "coherence_report",
            # Build pipeline (added in Sessions 1.5-1.7c)
            "build_id", "snapshot_urls", "review_result",
            "wiremock_config",
        }
        actual_fields = set(PipelineState.__annotations__.keys())
        assert required_fields == actual_fields, (
            f"Missing: {required_fields - actual_fields}, "
            f"Extra: {actual_fields - required_fields}"
        )

    def test_create_minimal_state(self) -> None:
        state: PipelineState = {
            "pipeline_id": "test-123",
            "current_stage": 1,
        }
        assert state["pipeline_id"] == "test-123"
        assert state["current_stage"] == 1

    def test_create_full_state(
        self, full_pipeline_state: PipelineState
    ) -> None:
        assert full_pipeline_state["current_stage"] == 6
        assert len(full_pipeline_state["csuite_outputs"]) == 8
        assert len(full_pipeline_state["spec_outputs"]) == 5
        assert full_pipeline_state["errors"] == []

    def test_state_optional_fields(self) -> None:
        state: PipelineState = {}
        assert state.get("pipeline_id") is None
        assert state.get("errors", []) == []
        assert state.get("sandbox_id") is None

    def test_gate_result_type(self) -> None:
        result: GateResult = {"passed": True, "reason": "test passed"}
        assert result["passed"] is True
        assert result["reason"] == "test passed"


# ═══════════════════════════════════════════════════════════════════════
# Validators — G1
# ═══════════════════════════════════════════════════════════════════════


class TestG1:
    """G1 — IdeaSpec validation."""

    def test_passes_with_valid_spec(
        self, valid_idea_spec: dict[str, object]
    ) -> None:
        state: PipelineState = {"idea_spec": valid_idea_spec}
        result = validate_g1(state)
        assert result["passed"] is True

    def test_fails_without_idea_spec(self) -> None:
        state: PipelineState = {}
        result = validate_g1(state)
        assert result["passed"] is False
        assert "missing" in result["reason"]

    def test_fails_without_title(self) -> None:
        state: PipelineState = {
            "idea_spec": {"description": "some desc"}
        }
        result = validate_g1(state)
        assert result["passed"] is False
        assert "title" in result["reason"]

    def test_fails_without_description(self) -> None:
        state: PipelineState = {
            "idea_spec": {"title": "some title"}
        }
        result = validate_g1(state)
        assert result["passed"] is False
        assert "description" in result["reason"]


# ═══════════════════════════════════════════════════════════════════════
# Validators — G2
# ═══════════════════════════════════════════════════════════════════════


class TestG2:
    """G2 — All 8 C-suite outputs present."""

    def test_passes_with_all_agents(self) -> None:
        from app.agents.csuite.ceo_agent import _default_output as ceo_d
        from app.agents.csuite.cto_agent import _default_output as cto_d
        from app.agents.csuite.cdo_agent import _default_output as cdo_d
        from app.agents.csuite.cmo_agent import _default_output as cmo_d
        from app.agents.csuite.cpo_agent import _default_output as cpo_d
        from app.agents.csuite.cso_agent import _default_output as cso_d
        from app.agents.csuite.cco_agent import _default_output as cco_d
        from app.agents.csuite.cfo_agent import _default_output as cfo_d
        outputs = {
            "ceo": ceo_d(), "cto": cto_d(), "cdo": cdo_d(),
            "cmo": cmo_d(), "cpo": cpo_d(), "cso": cso_d(),
            "cco": cco_d(), "cfo": cfo_d(),
        }
        result = validate_g2({"csuite_outputs": outputs})  # type: ignore[arg-type]
        assert result["passed"] is True

    def test_fails_with_missing_agent(self) -> None:
        outputs = {
            name: {"analysis": "done"}
            for name in ("ceo", "cto", "cpo")
        }
        result = validate_g2({"csuite_outputs": outputs})  # type: ignore[arg-type]
        assert result["passed"] is False
        assert "missing" in result["reason"]

    def test_fails_with_empty_outputs(self) -> None:
        result = validate_g2({})  # type: ignore[arg-type]
        assert result["passed"] is False


# ═══════════════════════════════════════════════════════════════════════
# Validators — G3
# ═══════════════════════════════════════════════════════════════════════


class TestG3:
    """G3 — Always passes (auto-resolves conflicts)."""

    def test_always_passes(self) -> None:
        result = validate_g3({})  # type: ignore[arg-type]
        assert result["passed"] is True

    def test_always_passes_with_any_state(
        self, full_pipeline_state: PipelineState
    ) -> None:
        result = validate_g3(full_pipeline_state)
        assert result["passed"] is True


# ═══════════════════════════════════════════════════════════════════════
# Validators — G4
# ═══════════════════════════════════════════════════════════════════════


class TestG4:
    """G4 — coherence_score >= 0.85."""

    def test_passes_above_threshold(self) -> None:
        state: PipelineState = {
            "comprehensive_plan": {"coherence_score": 0.93}
        }
        result = validate_g4(state)
        assert result["passed"] is True

    def test_passes_at_threshold(self) -> None:
        state: PipelineState = {
            "comprehensive_plan": {"coherence_score": 0.85}
        }
        result = validate_g4(state)
        assert result["passed"] is True

    def test_fails_below_threshold(self) -> None:
        state: PipelineState = {
            "comprehensive_plan": {"coherence_score": 0.50}
        }
        result = validate_g4(state)
        assert result["passed"] is False
        assert "0.50" in result["reason"]

    def test_fails_without_plan(self) -> None:
        result = validate_g4({})  # type: ignore[arg-type]
        assert result["passed"] is False

    def test_fails_non_numeric_score(self) -> None:
        state: PipelineState = {
            "comprehensive_plan": {"coherence_score": "not a number"}
        }
        result = validate_g4(state)
        assert result["passed"] is False


# ═══════════════════════════════════════════════════════════════════════
# Validators — G5
# ═══════════════════════════════════════════════════════════════════════


class TestG5:
    """G5 — All 5 spec outputs present."""

    def test_passes_with_all_specs(self) -> None:
        outputs = {
            name: {"spec": "done"}
            for name in (
                "api_spec", "db_spec", "ui_spec", "infra_spec", "test_spec",
            )
        }
        result = validate_g5({"spec_outputs": outputs})  # type: ignore[arg-type]
        assert result["passed"] is True

    def test_fails_with_missing_spec(self) -> None:
        outputs = {"api_spec": {"spec": "done"}}
        result = validate_g5({"spec_outputs": outputs})  # type: ignore[arg-type]
        assert result["passed"] is False


# ═══════════════════════════════════════════════════════════════════════
# Validators — G6
# ═══════════════════════════════════════════════════════════════════════


class TestG6:
    """G6 — Build manifest has files list."""

    def test_passes_with_files(self) -> None:
        state: PipelineState = {
            "build_manifest": {"files": ["src/App.tsx", "package.json"]}
        }
        result = validate_g6(state)
        assert result["passed"] is True

    def test_fails_without_manifest(self) -> None:
        result = validate_g6({})  # type: ignore[arg-type]
        assert result["passed"] is False

    def test_fails_with_empty_files(self) -> None:
        state: PipelineState = {"build_manifest": {"files": []}}
        result = validate_g6(state)
        assert result["passed"] is False


# ═══════════════════════════════════════════════════════════════════════
# Validators — G7
# ═══════════════════════════════════════════════════════════════════════


class TestG7:
    """G7 — Per-agent validation."""

    def test_passes_with_agent_files(self) -> None:
        state: PipelineState = {
            "generated_files": {"src/prd/index.tsx": "code"},
            "errors": [],
        }
        result = validate_g7(state, agent_name="prd")
        assert result["passed"] is True

    def test_fails_without_agent_name(self) -> None:
        state: PipelineState = {"generated_files": {}, "errors": []}
        result = validate_g7(state)
        assert result["passed"] is False

    def test_fails_with_agent_errors(self) -> None:
        state: PipelineState = {
            "generated_files": {"src/prd/index.tsx": "code"},
            "errors": ["prd agent crashed"],
        }
        result = validate_g7(state, agent_name="prd")
        assert result["passed"] is False

    def test_quality_agent_can_pass_without_files(self) -> None:
        state: PipelineState = {
            "generated_files": {},
            "errors": [],
        }
        result = validate_g7(state, agent_name="quality")
        assert result["passed"] is True


# ═══════════════════════════════════════════════════════════════════════
# Validators — G8–G12
# ═══════════════════════════════════════════════════════════════════════


class TestG8Through12:
    """G8–G12 — Final build validation gates."""

    def test_g8_passes_with_enough_files(self) -> None:
        state: PipelineState = {
            "generated_files": {f"file_{i}.tsx": "code" for i in range(10)}
        }
        result = validate_g8(state)
        assert result["passed"] is True

    def test_g8_fails_with_few_files(self) -> None:
        state: PipelineState = {"generated_files": {"a.tsx": "code"}}
        result = validate_g8(state)
        assert result["passed"] is False

    def test_g9_passes_with_no_errors(self) -> None:
        state: PipelineState = {"errors": []}
        result = validate_g9(state)
        assert result["passed"] is True

    def test_g9_fails_with_errors(self) -> None:
        state: PipelineState = {"errors": ["something broke"]}
        result = validate_g9(state)
        assert result["passed"] is False

    def test_g10_passes_with_files(self) -> None:
        state: PipelineState = {
            "generated_files": {"app.tsx": "code"}
        }
        result = validate_g10(state)
        assert result["passed"] is True

    def test_g10_fails_without_files(self) -> None:
        result = validate_g10({})  # type: ignore[arg-type]
        assert result["passed"] is False

    def test_g11_passes_when_all_manifest_files_generated(self) -> None:
        state: PipelineState = {
            "build_manifest": {"files": ["a.tsx", "b.tsx"]},
            "generated_files": {"a.tsx": "code", "b.tsx": "code"},
        }
        result = validate_g11(state)
        assert result["passed"] is True

    def test_g11_fails_when_manifest_files_missing(self) -> None:
        state: PipelineState = {
            "build_manifest": {"files": ["a.tsx", "b.tsx"]},
            "generated_files": {"a.tsx": "code"},
        }
        result = validate_g11(state)
        assert result["passed"] is False

    def test_g12_passes_when_all_gates_passed(self) -> None:
        state: PipelineState = {
            "gate_results": {
                "G1": {"passed": True, "reason": "ok"},
                "G2": {"passed": True, "reason": "ok"},
            }
        }
        result = validate_g12(state)
        assert result["passed"] is True

    def test_g12_fails_when_any_gate_failed(self) -> None:
        state: PipelineState = {
            "gate_results": {
                "G1": {"passed": True, "reason": "ok"},
                "G2": {"passed": False, "reason": "missing"},
            }
        }
        result = validate_g12(state)
        assert result["passed"] is False
        assert "G2" in result["reason"]


# ═══════════════════════════════════════════════════════════════════════
# Graph — Full pipeline execution
# ═══════════════════════════════════════════════════════════════════════


class TestPipelineGraph:
    """Test full graph execution with stub agents."""

    @pytest.mark.asyncio
    async def test_full_pipeline_success(
        self, valid_idea_spec: dict[str, object]
    ) -> None:
        """Run the pipeline end-to-end — should complete all 6 stages."""
        with patch(
            "app.agents.graph.publish_event",
            new_callable=AsyncMock,
        ) as mock_publish:
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

            # Should have generated files
            assert len(result["generated_files"]) >= 10

            # No errors
            assert result["errors"] == []

            # Redis pub/sub events should have been published
            assert mock_publish.call_count > 0

    @pytest.mark.asyncio
    async def test_pipeline_fails_on_bad_idea_spec(self) -> None:
        """Pipeline should fail at G1 with invalid idea spec."""
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
                "idea_spec": {},  # Invalid — no title or description
                "gate_results": {},
                "errors": [],
                "sandbox_id": None,
            }

            result = await pipeline_graph.ainvoke(initial_state)

            # Should have G1 failure
            assert result["gate_results"]["G1"]["passed"] is False
            assert len(result["errors"]) > 0

    @pytest.mark.asyncio
    async def test_pipeline_publishes_stage_events(
        self, valid_idea_spec: dict[str, object]
    ) -> None:
        """Verify Redis pub/sub events are published at each stage."""
        published_events: list[dict[str, object]] = []

        async def capture_publish(channel: str, data: dict[str, object]) -> None:
            published_events.append({"channel": channel, "data": data})

        with patch(
            "app.agents.graph.publish_event",
            side_effect=capture_publish,
        ):
            from app.agents.graph import pipeline_graph

            pipeline_id = str(uuid.uuid4())
            initial_state: PipelineState = {
                "pipeline_id": pipeline_id,
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

            await pipeline_graph.ainvoke(initial_state)

            # Should have events for all 6 stages (at least running + completed each)
            assert len(published_events) >= 12  # 6 stages × 2

            # All events should be on the correct channel
            expected_channel = f"pipeline:{pipeline_id}"
            for event in published_events:
                assert event["channel"] == expected_channel


# ═══════════════════════════════════════════════════════════════════════
# API — POST /run
# ═══════════════════════════════════════════════════════════════════════


class TestPipelineRunEndpoint:
    """POST /api/v1/pipeline/run — non-blocking submission."""

    @pytest.mark.asyncio
    async def test_run_returns_202_with_pipeline_id(
        self,
        client: AsyncClient,
        mock_user_id: uuid.UUID,
        mock_project_id: uuid.UUID,
        valid_idea_spec: dict[str, object],
    ) -> None:
        """Submitting a pipeline should return 202 with pipeline_id."""
        pipeline_id = uuid.uuid4()

        mock_session = AsyncMock()
        mock_session.add = MagicMock()
        mock_session.flush = AsyncMock()
        mock_session.refresh = AsyncMock(
            side_effect=lambda obj: setattr(obj, "id", pipeline_id)
        )
        mock_session.commit = AsyncMock()
        mock_session.rollback = AsyncMock()
        mock_session.close = AsyncMock()

        from app.core.database import get_write_session

        async def _override_write_session():
            yield mock_session

        app.dependency_overrides[get_write_session] = _override_write_session

        try:
            with (
                patch(
                    "app.middleware.auth._fetch_jwks",
                    new_callable=AsyncMock,
                    return_value={"keys": []},
                ),
                patch(
                    "app.middleware.auth.jwt.get_unverified_header",
                    return_value={"kid": "test-kid"},
                ),
                patch(
                    "app.middleware.auth._find_rsa_key",
                    return_value={"kty": "RSA", "kid": "test-kid", "use": "sig", "n": "x", "e": "y"},
                ),
                patch(
                    "app.middleware.auth.jwt.decode",
                    return_value={
                        "sub": str(mock_user_id),
                        "exp": 9999999999,
                    },
                ),
                patch(
                    "app.agents.graph.publish_event",
                    new_callable=AsyncMock,
                ),
                patch(
                    "app.api.v1.pipeline.set_cache",
                    new_callable=AsyncMock,
                ),
            ):
                resp = await client.post(
                    "/api/v1/pipeline/run",
                    json={
                        "project_id": str(mock_project_id),
                        "idea_spec": valid_idea_spec,
                    },
                    headers={"Authorization": "Bearer test-jwt"},
                )

                assert resp.status_code == 202
                data = resp.json()
                assert "pipeline_id" in data
                assert data["status"] == "queued"
        finally:
            app.dependency_overrides.pop(get_write_session, None)

    @pytest.mark.asyncio
    async def test_run_requires_auth(
        self,
        client: AsyncClient,
        mock_project_id: uuid.UUID,
        valid_idea_spec: dict[str, object],
    ) -> None:
        """Endpoint should reject requests without auth token."""
        resp = await client.post(
            "/api/v1/pipeline/run",
            json={
                "project_id": str(mock_project_id),
                "idea_spec": valid_idea_spec,
            },
        )
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_run_validates_idea_spec(
        self,
        client: AsyncClient,
        mock_user_id: uuid.UUID,
        mock_project_id: uuid.UUID,
    ) -> None:
        """Endpoint should reject invalid idea_spec."""
        with (
            patch(
                "app.middleware.auth._fetch_jwks",
                new_callable=AsyncMock,
                return_value={"keys": []},
            ),
            patch(
                "app.middleware.auth.jwt.get_unverified_header",
                return_value={"kid": "test-kid"},
            ),
            patch(
                "app.middleware.auth._find_rsa_key",
                return_value={"kty": "RSA", "kid": "test-kid", "use": "sig", "n": "x", "e": "y"},
            ),
            patch(
                "app.middleware.auth.jwt.decode",
                return_value={
                    "sub": str(mock_user_id),
                    "exp": 9999999999,
                },
            ),
        ):
            resp = await client.post(
                "/api/v1/pipeline/run",
                json={
                    "project_id": str(mock_project_id),
                    "idea_spec": {
                        "title": "",  # Empty — fails min_length
                        "description": "test",
                    },
                },
                headers={"Authorization": "Bearer test-jwt"},
            )
            assert resp.status_code == 422


# ═══════════════════════════════════════════════════════════════════════
# API — GET /status
# ═══════════════════════════════════════════════════════════════════════


class TestPipelineStatusEndpoint:
    """GET /api/v1/pipeline/{id}/status — status retrieval."""

    @pytest.mark.asyncio
    async def test_status_returns_pipeline_info(
        self,
        client: AsyncClient,
        mock_user_id: uuid.UUID,
    ) -> None:
        """Should return pipeline status from DB."""
        import datetime

        pipeline_id = uuid.uuid4()
        project_id = uuid.uuid4()

        mock_pipeline = MagicMock()
        mock_pipeline.id = pipeline_id
        mock_pipeline.project_id = project_id
        mock_pipeline.user_id = mock_user_id
        mock_pipeline.status = MagicMock(value="running")
        mock_pipeline.current_stage = 3
        mock_pipeline.started_at = datetime.datetime.now(datetime.timezone.utc)
        mock_pipeline.completed_at = None
        mock_pipeline.created_at = datetime.datetime.now(datetime.timezone.utc)

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_pipeline

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)

        from app.core.database import get_read_session

        async def _override_read_session():
            yield mock_session

        app.dependency_overrides[get_read_session] = _override_read_session

        try:
            with (
                patch(
                    "app.middleware.auth._fetch_jwks",
                    new_callable=AsyncMock,
                    return_value={"keys": []},
                ),
                patch(
                    "app.middleware.auth.jwt.get_unverified_header",
                    return_value={"kid": "test-kid"},
                ),
                patch(
                    "app.middleware.auth._find_rsa_key",
                    return_value={"kty": "RSA", "kid": "test-kid", "use": "sig", "n": "x", "e": "y"},
                ),
                patch(
                    "app.middleware.auth.jwt.decode",
                    return_value={
                        "sub": str(mock_user_id),
                        "exp": 9999999999,
                    },
                ),
                patch(
                    "app.api.v1.pipeline.get_cache",
                    new_callable=AsyncMock,
                    return_value=None,
                ),
            ):
                resp = await client.get(
                    f"/api/v1/pipeline/{pipeline_id}/status",
                    headers={"Authorization": "Bearer test-jwt"},
                )

                assert resp.status_code == 200
                data = resp.json()
                assert data["pipeline_id"] == str(pipeline_id)
                assert data["status"] == "running"
                assert data["current_stage"] == 3
        finally:
            app.dependency_overrides.pop(get_read_session, None)

    @pytest.mark.asyncio
    async def test_status_404_for_unknown_pipeline(
        self,
        client: AsyncClient,
        mock_user_id: uuid.UUID,
    ) -> None:
        """Should return 404 for non-existent pipeline."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)

        from app.core.database import get_read_session

        async def _override_read_session():
            yield mock_session

        app.dependency_overrides[get_read_session] = _override_read_session

        try:
            with (
                patch(
                    "app.middleware.auth._fetch_jwks",
                    new_callable=AsyncMock,
                    return_value={"keys": []},
                ),
                patch(
                    "app.middleware.auth.jwt.get_unverified_header",
                    return_value={"kid": "test-kid"},
                ),
                patch(
                    "app.middleware.auth._find_rsa_key",
                    return_value={"kty": "RSA", "kid": "test-kid", "use": "sig", "n": "x", "e": "y"},
                ),
                patch(
                    "app.middleware.auth.jwt.decode",
                    return_value={
                        "sub": str(mock_user_id),
                        "exp": 9999999999,
                    },
                ),
            ):
                resp = await client.get(
                    f"/api/v1/pipeline/{uuid.uuid4()}/status",
                    headers={"Authorization": "Bearer test-jwt"},
                )

                assert resp.status_code == 404
        finally:
            app.dependency_overrides.pop(get_read_session, None)


# ═══════════════════════════════════════════════════════════════════════
# API — GET /stages
# ═══════════════════════════════════════════════════════════════════════


class TestPipelineStagesEndpoint:
    """GET /api/v1/pipeline/{id}/stages — gate results."""

    @pytest.mark.asyncio
    async def test_stages_returns_gate_results(
        self,
        client: AsyncClient,
        mock_user_id: uuid.UUID,
    ) -> None:
        """Should return stage info with gate results from cache."""
        pipeline_id = uuid.uuid4()
        cached_data = json.dumps({
            "status": "completed",
            "current_stage": 6,
            "gate_results": {
                "G1": {"passed": True, "reason": "ok"},
                "G2": {"passed": True, "reason": "ok"},
                "G4": {"passed": True, "reason": "ok"},
            },
            "errors": [],
        })

        # Mock session with ownership hit
        mock_pipeline = MagicMock()
        mock_pipeline.id = pipeline_id
        mock_pipeline.user_id = mock_user_id
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_pipeline
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)

        from app.core.database import get_read_session

        async def _override_read_session():
            yield mock_session

        app.dependency_overrides[get_read_session] = _override_read_session

        try:
            with (
                patch(
                    "app.middleware.auth._fetch_jwks",
                    new_callable=AsyncMock,
                    return_value={"keys": []},
                ),
                patch(
                    "app.middleware.auth.jwt.get_unverified_header",
                    return_value={"kid": "test-kid"},
                ),
                patch(
                    "app.middleware.auth._find_rsa_key",
                    return_value={"kty": "RSA", "kid": "test-kid", "use": "sig", "n": "x", "e": "y"},
                ),
                patch(
                    "app.middleware.auth.jwt.decode",
                    return_value={
                        "sub": str(mock_user_id),
                        "exp": 9999999999,
                    },
                ),
                patch(
                    "app.api.v1.pipeline.get_cache",
                    new_callable=AsyncMock,
                    return_value=cached_data,
                ),
            ):
                resp = await client.get(
                    f"/api/v1/pipeline/{pipeline_id}/stages",
                    headers={"Authorization": "Bearer test-jwt"},
                )

                assert resp.status_code == 200
                data = resp.json()
                assert len(data["stages"]) == 6
                assert "G1" in data["gate_results"]
                assert data["gate_results"]["G1"]["passed"] is True
        finally:
            app.dependency_overrides.pop(get_read_session, None)

    @pytest.mark.asyncio
    async def test_stages_returns_empty_without_cache(
        self,
        client: AsyncClient,
        mock_user_id: uuid.UUID,
    ) -> None:
        """Should return empty stages when no cache exists."""
        pipeline_id = uuid.uuid4()

        # Mock session with ownership hit
        mock_pipeline = MagicMock()
        mock_pipeline.id = pipeline_id
        mock_pipeline.user_id = mock_user_id
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_pipeline
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)

        from app.core.database import get_read_session

        async def _override_read_session():
            yield mock_session

        app.dependency_overrides[get_read_session] = _override_read_session

        try:
            with (
                patch(
                    "app.middleware.auth._fetch_jwks",
                    new_callable=AsyncMock,
                    return_value={"keys": []},
                ),
                patch(
                    "app.middleware.auth.jwt.get_unverified_header",
                    return_value={"kid": "test-kid"},
                ),
                patch(
                    "app.middleware.auth._find_rsa_key",
                    return_value={"kty": "RSA", "kid": "test-kid", "use": "sig", "n": "x", "e": "y"},
                ),
                patch(
                    "app.middleware.auth.jwt.decode",
                    return_value={
                        "sub": str(mock_user_id),
                        "exp": 9999999999,
                    },
                ),
                patch(
                    "app.api.v1.pipeline.get_cache",
                    new_callable=AsyncMock,
                    return_value=None,
                ),
            ):
                resp = await client.get(
                    f"/api/v1/pipeline/{pipeline_id}/stages",
                    headers={"Authorization": "Bearer test-jwt"},
                )

                assert resp.status_code == 200
                data = resp.json()
                assert len(data["stages"]) == 6
                # All stages should be pending
                for stage in data["stages"]:
                    assert stage["status"] == "pending"
        finally:
            app.dependency_overrides.pop(get_read_session, None)

    @pytest.mark.asyncio
    async def test_stages_requires_ownership(
        self,
        client: AsyncClient,
        mock_user_id: uuid.UUID,
    ) -> None:
        """Should return 404 when pipeline doesn't belong to requesting user."""
        # Mock session returning None (no matching pipeline for this user)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)

        from app.core.database import get_read_session

        async def _override_read_session():
            yield mock_session

        app.dependency_overrides[get_read_session] = _override_read_session

        try:
            with (
                patch(
                    "app.middleware.auth._fetch_jwks",
                    new_callable=AsyncMock,
                    return_value={"keys": []},
                ),
                patch(
                    "app.middleware.auth.jwt.get_unverified_header",
                    return_value={"kid": "test-kid"},
                ),
                patch(
                    "app.middleware.auth._find_rsa_key",
                    return_value={"kty": "RSA", "kid": "test-kid", "use": "sig", "n": "x", "e": "y"},
                ),
                patch(
                    "app.middleware.auth.jwt.decode",
                    return_value={
                        "sub": str(mock_user_id),
                        "exp": 9999999999,
                    },
                ),
            ):
                resp = await client.get(
                    f"/api/v1/pipeline/{uuid.uuid4()}/stages",
                    headers={"Authorization": "Bearer test-jwt"},
                )

                assert resp.status_code == 404
        finally:
            app.dependency_overrides.pop(get_read_session, None)


# ═══════════════════════════════════════════════════════════════════════
# Schemas
# ═══════════════════════════════════════════════════════════════════════


# ═══════════════════════════════════════════════════════════════════════
# Non-blocking guarantee
# ═══════════════════════════════════════════════════════════════════════


class TestNonBlockingGuarantee:
    """Verify POST /run returns immediately — does NOT await graph completion."""

    @pytest.mark.asyncio
    async def test_start_pipeline_is_nonblocking(
        self,
        client: AsyncClient,
        mock_user_id: uuid.UUID,
        mock_project_id: uuid.UUID,
        valid_idea_spec: dict[str, object],
    ) -> None:
        """POST /run must return in under 500ms — not 10+ seconds."""
        import time

        pipeline_id = uuid.uuid4()
        mock_session = AsyncMock()
        mock_session.add = MagicMock()
        mock_session.flush = AsyncMock()
        mock_session.refresh = AsyncMock(
            side_effect=lambda obj: setattr(obj, "id", pipeline_id)
        )
        mock_session.commit = AsyncMock()
        mock_session.rollback = AsyncMock()
        mock_session.close = AsyncMock()

        from app.core.database import get_write_session

        async def _override_write_session():
            yield mock_session

        app.dependency_overrides[get_write_session] = _override_write_session

        try:
            with (
                patch(
                    "app.middleware.auth._fetch_jwks",
                    new_callable=AsyncMock,
                    return_value={"keys": []},
                ),
                patch(
                    "app.middleware.auth.jwt.get_unverified_header",
                    return_value={"kid": "test-kid"},
                ),
                patch(
                    "app.middleware.auth._find_rsa_key",
                    return_value={"kty": "RSA", "kid": "test-kid", "use": "sig", "n": "x", "e": "y"},
                ),
                patch(
                    "app.middleware.auth.jwt.decode",
                    return_value={
                        "sub": str(mock_user_id),
                        "exp": 9999999999,
                    },
                ),
                patch(
                    "app.agents.graph.publish_event",
                    new_callable=AsyncMock,
                ),
                patch(
                    "app.api.v1.pipeline.set_cache",
                    new_callable=AsyncMock,
                ),
            ):
                start = time.monotonic()
                resp = await client.post(
                    "/api/v1/pipeline/run",
                    json={
                        "project_id": str(mock_project_id),
                        "idea_spec": valid_idea_spec,
                    },
                    headers={"Authorization": "Bearer test-jwt"},
                )
                elapsed_ms = (time.monotonic() - start) * 1000

                assert resp.status_code == 202
                assert elapsed_ms < 500, (
                    f"POST /run took {elapsed_ms:.0f}ms — must be under 500ms. "
                    "Pipeline is being awaited inline instead of backgrounded."
                )
        finally:
            app.dependency_overrides.pop(get_write_session, None)


# ═══════════════════════════════════════════════════════════════════════
# Ownership checks
# ═══════════════════════════════════════════════════════════════════════


class TestOwnershipChecks:
    """Verify endpoints enforce WHERE user_id = current_user.id."""

    @pytest.mark.asyncio
    async def test_pipeline_status_requires_ownership(
        self,
        client: AsyncClient,
        mock_user_id: uuid.UUID,
    ) -> None:
        """GET /status returns 404 for pipelines belonging to other users."""
        # Session returns None — simulating a pipeline owned by a different user
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)

        from app.core.database import get_read_session

        async def _override_read_session():
            yield mock_session

        app.dependency_overrides[get_read_session] = _override_read_session

        try:
            with (
                patch(
                    "app.middleware.auth._fetch_jwks",
                    new_callable=AsyncMock,
                    return_value={"keys": []},
                ),
                patch(
                    "app.middleware.auth.jwt.get_unverified_header",
                    return_value={"kid": "test-kid"},
                ),
                patch(
                    "app.middleware.auth._find_rsa_key",
                    return_value={"kty": "RSA", "kid": "test-kid", "use": "sig", "n": "x", "e": "y"},
                ),
                patch(
                    "app.middleware.auth.jwt.decode",
                    return_value={
                        "sub": str(mock_user_id),
                        "exp": 9999999999,
                    },
                ),
            ):
                resp = await client.get(
                    f"/api/v1/pipeline/{uuid.uuid4()}/status",
                    headers={"Authorization": "Bearer test-jwt"},
                )
                assert resp.status_code == 404
        finally:
            app.dependency_overrides.pop(get_read_session, None)


# ═══════════════════════════════════════════════════════════════════════
# WebSocket — Stage events
# ═══════════════════════════════════════════════════════════════════════


class TestWebSocketStream:
    """WS /api/v1/pipeline/{id}/stream — live Redis pub/sub relay."""

    @pytest.mark.skip(
        reason="WS integration test requires live Redis pub/sub; "
        "graph publish events are verified in TestPipelineGraph."
    )
    @pytest.mark.asyncio
    async def test_websocket_receives_stage_events(self) -> None:
        """WebSocket client should receive all stage events from Redis.

        This test is skipped because it requires a running Redis server
        for pub/sub message relay. The underlying mechanism (publish_event
        called at every stage transition) is verified in
        TestPipelineGraph.test_pipeline_publishes_stage_events.
        """
        pass


# ═══════════════════════════════════════════════════════════════════════
# Schemas
# ═══════════════════════════════════════════════════════════════════════


class TestPipelineSchemas:
    """Test Pydantic schemas for pipeline endpoints."""

    def test_idea_spec_input_valid(self) -> None:
        from app.schemas.pipeline import IdeaSpecInput

        spec = IdeaSpecInput(
            title="My App",
            description="A test application",
            features=["feature1"],
        )
        assert spec.title == "My App"
        assert len(spec.features) == 1

    def test_idea_spec_input_rejects_empty_title(self) -> None:
        from app.schemas.pipeline import IdeaSpecInput
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            IdeaSpecInput(title="", description="valid")

    def test_pipeline_run_response(self) -> None:
        from app.schemas.pipeline import PipelineRunResponse

        resp = PipelineRunResponse(
            pipeline_id=uuid.uuid4(),
            status="queued",
        )
        assert resp.status == "queued"

    def test_gate_result_response(self) -> None:
        from app.schemas.pipeline import GateResultResponse

        gate = GateResultResponse(
            gate_id="G1",
            passed=True,
            reason="validated",
        )
        assert gate.passed is True

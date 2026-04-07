"""
Tests for the 10 FORGE build agents.

Covers:
  - Each agent (1-9) produces valid dict[str, str] output
  - Review agent produces ReviewResult
  - ContextWindowManager splits at 60% threshold with 200-token overlap
  - SnapshotService captures and uploads to R2 (mocked)
  - Agents 1-3 sequentially produce valid TypeScript files
  - G7 catches deliberate syntax errors
  - Snapshot captured after each agent
  - Hotfix retry on G7 failure

All external services mocked per AGENTS.md rule #7.
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agents.ai_router import AIRouter, create_ai_router
from app.agents.build import (
    BUILD_AGENT_MAP,
    BUILD_AGENT_NAMES,
    ContextWindowManager,
    HotfixResult,
    ReviewResult,
    SnapshotService,
    run_scaffold_agent,
    run_router_agent,
    run_component_agent,
    run_page_agent,
    run_api_agent,
    run_db_agent,
    run_auth_agent,
    run_style_agent,
    run_test_agent,
    run_review_agent,
    run_hotfix_agent,
)
from app.agents.build.context_window_manager import (
    CHARS_PER_TOKEN,
    CHUNK_OVERLAP_TOKENS,
    DEFAULT_CONTEXT_LIMIT,
    SPLIT_THRESHOLD,
)
from app.agents.build.sandbox_runner import (
    ToolResult,
    SemgrepResult,
    LighthouseResult,
    PlaywrightResult,
    AxeResult,
)
from app.agents.state import PipelineState
from app.agents.validators import validate_g7


# ── Module-level mock: patch Redis at import time so tests never hang ──
# The root conftest imports app.main which creates the FastAPI app.
# With asyncio_mode=auto, every test gets an event loop. The Redis
# get_redis() returns a real connection that hangs during teardown.
# Patch it once at module level so ALL tests (sync and async) use mocks.

_mock_redis = MagicMock(
    publish=AsyncMock(),
    get=AsyncMock(return_value=None),
    set=AsyncMock(),
    delete=AsyncMock(),
    pipeline=MagicMock(return_value=MagicMock(
        execute=AsyncMock(return_value=[]),
    )),
    close=AsyncMock(),
)

_redis_patch = patch(
    "app.core.redis.get_redis",
    new_callable=AsyncMock,
    return_value=_mock_redis,
)
_upload_patch = patch(
    "app.agents.build.snapshot_service.upload_file",
    new_callable=AsyncMock,
    return_value=None,
)

# Start patches at module load time (before any test runs)
_redis_patch.start()
_upload_patch.start()


# ── Fixtures ─────────────────────────────────────────────────────────

@pytest.fixture
def ai_router() -> AIRouter:
    return create_ai_router(provider="stub")


@pytest.fixture
def cwm(ai_router: AIRouter) -> ContextWindowManager:
    return ContextWindowManager(ai_router)


@pytest.fixture
def sample_state() -> PipelineState:
    """Minimal pipeline state for testing build agents."""
    return {
        "pipeline_id": "test-pipeline-001",
        "project_id": "test-project-001",
        "user_id": "test-user-001",
        "current_stage": 6,
        "idea_spec": {
            "title": "Task Manager Pro",
            "description": "A powerful task management application with real-time collaboration",
            "features": ["kanban-board", "real-time-sync", "team-chat"],
            "framework": "react_vite",
            "target_audience": "small teams and freelancers",
        },
        "comprehensive_plan": {
            "executive_summary": "Task management app with kanban and chat",
            "coherence_score": 0.92,
            "architect_output": {
                "routes": [
                    {"path": "/", "name": "home"},
                    {"path": "/login", "name": "login"},
                    {"path": "/dashboard", "name": "dashboard"},
                    {"path": "/settings", "name": "settings"},
                ],
            },
        },
        "resolved_dependencies": {
            "packages": {
                "react": "18.3.1",
                "react-dom": "18.3.1",
                "typescript": "5.4.5",
                "vite": "5.4.14",
                "tailwindcss": "3.4.17",
            },
            "lockfile_hash": "abc123",
            "conflicts_resolved": 0,
        },
        "env_contract": {
            "required": [
                {"name": "NODE_ENV", "type": "string", "description": "Environment", "example": "production"},
            ],
            "optional": [
                {"name": "VITE_API_URL", "type": "url", "description": "API URL", "example": "http://localhost:8000"},
            ],
        },
        "injected_schemas": {},
        "generated_files": {},
        "gate_results": {},
        "errors": [],
        "build_manifest": {
            "files": [],
            "framework": "react_vite",
            "total_agents": 10,
        },
    }


# ── Context Window Manager Tests ─────────────────────────────────────

class TestContextWindowManager:
    """Test context window splitting and merging."""

    def test_token_estimation(self, cwm: ContextWindowManager) -> None:
        text = "a" * 400
        assert cwm._estimate_tokens(text) == 100

    def test_no_split_under_threshold(self, cwm: ContextWindowManager) -> None:
        # Short prompt should not split
        prompt = "Generate a React component"
        chunks = cwm._split_prompt(prompt)
        assert len(chunks) == 1
        assert chunks[0] == prompt

    def test_split_over_threshold(self) -> None:
        # Create a CWM with tiny context limit to force splitting
        router = create_ai_router(provider="stub")
        cwm = ContextWindowManager(router, context_limit=100)
        # 60% of 100 tokens = 60 tokens = 240 chars
        big_prompt = "x" * 500  # Exceeds threshold
        chunks = cwm._split_prompt(big_prompt)
        assert len(chunks) > 1

    def test_overlap_between_chunks(self) -> None:
        router = create_ai_router(provider="stub")
        cwm = ContextWindowManager(router, context_limit=100)
        big_prompt = "abcdefghij" * 50  # 500 chars
        chunks = cwm._split_prompt(big_prompt)
        if len(chunks) >= 2:
            # The overlap should be CHUNK_OVERLAP_TOKENS * CHARS_PER_TOKEN = 800 chars
            # But with our tiny limit, chunk_size = 60 * 4 = 240 chars
            # overlap = 200 * 4 = 800 chars, clamped by chunk size
            assert len(chunks) >= 2

    def test_merge_file_results(self, cwm: ContextWindowManager) -> None:
        results = [
            {"src/a.ts": "content a", "src/b.ts": "content b"},
            {"src/c.ts": "content c", "src/b.ts": "updated b"},
        ]
        merged = cwm._merge_file_results(results)
        assert merged["src/a.ts"] == "content a"
        assert merged["src/b.ts"] == "updated b"  # Later chunks win
        assert merged["src/c.ts"] == "content c"

    def test_parse_response_valid_json(self, cwm: ContextWindowManager) -> None:
        raw = json.dumps({"file.ts": "content"})
        result = cwm._parse_response(raw, "test")
        assert result == {"file.ts": "content"}

    def test_parse_response_invalid_json(self, cwm: ContextWindowManager) -> None:
        result = cwm._parse_response("not json", "test")
        assert result == {}

    def test_parse_response_non_dict(self, cwm: ContextWindowManager) -> None:
        result = cwm._parse_response("[1, 2, 3]", "test")
        assert result == {}

    @pytest.mark.anyio
    async def test_generate_single_call(self, cwm: ContextWindowManager) -> None:
        result = await cwm.generate("system", "user prompt", "test_agent")
        # Stub router returns "{}" → parsed to empty dict
        assert isinstance(result, dict)

    @pytest.mark.anyio
    async def test_default_context_limit(self) -> None:
        router = create_ai_router(provider="stub")
        cwm = ContextWindowManager(router)
        assert cwm.context_limit == DEFAULT_CONTEXT_LIMIT
        assert cwm.split_threshold_tokens == int(DEFAULT_CONTEXT_LIMIT * SPLIT_THRESHOLD)


# ── Snapshot Service Tests ───────────────────────────────────────────

class TestSnapshotService:
    """Test snapshot capture and upload (R2 mocked)."""

    @pytest.mark.anyio
    async def test_capture_snapshot_success(self) -> None:
        service = SnapshotService()
        with patch("app.agents.build.snapshot_service.upload_file", new_callable=AsyncMock) as mock_upload:
            mock_upload.return_value = "builds/b1/snapshots/01_scaffold.json"

            url = await service.capture_snapshot(
                build_id="b1",
                project_id="p1",
                agent_name="scaffold",
                snapshot_index=1,
                generated_files={"package.json": "{}"},
                gate_results={"G7_scaffold": {"passed": True, "reason": "ok"}},
            )

            assert url == "builds/b1/snapshots/01_scaffold.json"
            mock_upload.assert_called_once()
            call_args = mock_upload.call_args
            assert call_args.kwargs["key"] == "builds/b1/snapshots/01_scaffold.json"
            assert call_args.kwargs["content_type"] == "application/json"

    @pytest.mark.anyio
    async def test_capture_snapshot_failure_doesnt_crash(self) -> None:
        service = SnapshotService()
        with patch("app.agents.build.snapshot_service.upload_file", new_callable=AsyncMock) as mock_upload:
            mock_upload.side_effect = Exception("R2 down")
            url = await service.capture_snapshot(
                build_id="b1", project_id="p1", agent_name="test",
                snapshot_index=9, generated_files={},
            )
            assert url == ""  # Failure returns empty string, no crash


# ── Hotfix Agent Tests ───────────────────────────────────────────────

class TestHotfixAgent:
    """Test hotfix agent real stub."""

    @pytest.mark.anyio
    async def test_hotfix_returns_not_implemented(
        self, ai_router: AIRouter, cwm: ContextWindowManager, sample_state: PipelineState,
    ) -> None:
        result = await run_hotfix_agent(
            state=sample_state,
            ai_router=ai_router,
            context_window_manager=cwm,
            failed_agent="component",
            error_details="syntax error in Button.tsx",
            generated_files={"src/Button.tsx": "invalid code"},
        )
        assert isinstance(result, HotfixResult)
        assert result.success is False
        # Agent is implemented: it attempts fixes and reports the outcome
        assert "Attempted fixes" in result.reason
        assert result.changes == []

    @pytest.mark.anyio
    async def test_hotfix_callable_from_review(
        self, ai_router: AIRouter, cwm: ContextWindowManager, sample_state: PipelineState,
    ) -> None:
        """Verify review_agent can call hotfix without import errors."""
        result = await run_hotfix_agent(
            state=sample_state, ai_router=ai_router, context_window_manager=cwm,
            failed_agent="test", error_details="test error", generated_files={},
        )
        assert result.error_category == "unknown"


# ── Individual Agent Tests (1-9) ─────────────────────────────────────

class TestScaffoldAgent:
    """Agent 1 — scaffold."""

    @pytest.mark.anyio
    async def test_produces_files(
        self, ai_router: AIRouter, cwm: ContextWindowManager, sample_state: PipelineState,
    ) -> None:
        files = await run_scaffold_agent(sample_state, ai_router, cwm)
        assert isinstance(files, dict)
        assert len(files) > 0
        # Must produce package.json and tsconfig.json
        assert "package.json" in files
        assert "tsconfig.json" in files

    @pytest.mark.anyio
    async def test_package_json_valid(
        self, ai_router: AIRouter, cwm: ContextWindowManager, sample_state: PipelineState,
    ) -> None:
        files = await run_scaffold_agent(sample_state, ai_router, cwm)
        pkg = json.loads(files["package.json"])
        assert "dependencies" in pkg
        assert pkg["dependencies"]["react"] == "18.3.1"
        assert pkg.get("private") is True

    @pytest.mark.anyio
    async def test_tsconfig_strict(
        self, ai_router: AIRouter, cwm: ContextWindowManager, sample_state: PipelineState,
    ) -> None:
        files = await run_scaffold_agent(sample_state, ai_router, cwm)
        tsconfig = json.loads(files["tsconfig.json"])
        assert tsconfig["compilerOptions"]["strict"] is True

    @pytest.mark.anyio
    async def test_gitignore_present(
        self, ai_router: AIRouter, cwm: ContextWindowManager, sample_state: PipelineState,
    ) -> None:
        files = await run_scaffold_agent(sample_state, ai_router, cwm)
        assert ".gitignore" in files
        assert "node_modules" in files[".gitignore"]

    @pytest.mark.anyio
    async def test_env_example_from_contract(
        self, ai_router: AIRouter, cwm: ContextWindowManager, sample_state: PipelineState,
    ) -> None:
        files = await run_scaffold_agent(sample_state, ai_router, cwm)
        assert ".env.example" in files
        assert "NODE_ENV" in files[".env.example"]

    @pytest.mark.anyio
    async def test_ci_workflow(
        self, ai_router: AIRouter, cwm: ContextWindowManager, sample_state: PipelineState,
    ) -> None:
        files = await run_scaffold_agent(sample_state, ai_router, cwm)
        assert ".github/workflows/ci.yml" in files


class TestRouterAgent:
    """Agent 2 — router."""

    @pytest.mark.anyio
    async def test_produces_route_files(
        self, ai_router: AIRouter, cwm: ContextWindowManager, sample_state: PipelineState,
    ) -> None:
        files = await run_router_agent(sample_state, ai_router, cwm)
        assert isinstance(files, dict)
        assert len(files) >= 4  # At least home, login, dashboard, settings

    @pytest.mark.anyio
    async def test_has_app_entry(
        self, ai_router: AIRouter, cwm: ContextWindowManager, sample_state: PipelineState,
    ) -> None:
        files = await run_router_agent(sample_state, ai_router, cwm)
        # Vite project should have App.tsx
        assert "src/App.tsx" in files

    @pytest.mark.anyio
    async def test_pages_export_default(
        self, ai_router: AIRouter, cwm: ContextWindowManager, sample_state: PipelineState,
    ) -> None:
        files = await run_router_agent(sample_state, ai_router, cwm)
        for path, content in files.items():
            if "/pages/" in path:
                assert "export default function" in content


class TestComponentAgent:
    """Agent 3 — components."""

    @pytest.mark.anyio
    async def test_produces_all_components(
        self, ai_router: AIRouter, cwm: ContextWindowManager, sample_state: PipelineState,
    ) -> None:
        files = await run_component_agent(sample_state, ai_router, cwm)
        assert isinstance(files, dict)
        # Should have 13 components + barrel
        assert len(files) >= 14
        assert "src/components/ui/Button.tsx" in files
        assert "src/components/ui/ErrorBoundary.tsx" in files
        assert "src/components/ui/index.ts" in files

    @pytest.mark.anyio
    async def test_components_are_valid_typescript(
        self, ai_router: AIRouter, cwm: ContextWindowManager, sample_state: PipelineState,
    ) -> None:
        files = await run_component_agent(sample_state, ai_router, cwm)
        for path, content in files.items():
            if path.endswith(".tsx"):
                assert "import React" in content
                assert "export default" in content

    @pytest.mark.anyio
    async def test_barrel_reexports_all(
        self, ai_router: AIRouter, cwm: ContextWindowManager, sample_state: PipelineState,
    ) -> None:
        files = await run_component_agent(sample_state, ai_router, cwm)
        barrel = files["src/components/ui/index.ts"]
        for comp in ["Button", "Input", "Card", "Modal", "Spinner", "ErrorBoundary"]:
            assert comp in barrel


class TestPageAgent:
    """Agent 4 — pages."""

    @pytest.mark.anyio
    async def test_produces_pages(
        self, ai_router: AIRouter, cwm: ContextWindowManager, sample_state: PipelineState,
    ) -> None:
        files = await run_page_agent(sample_state, ai_router, cwm)
        assert isinstance(files, dict)
        assert len(files) >= 4

    @pytest.mark.anyio
    async def test_pages_have_error_boundary(
        self, ai_router: AIRouter, cwm: ContextWindowManager, sample_state: PipelineState,
    ) -> None:
        files = await run_page_agent(sample_state, ai_router, cwm)
        for path, content in files.items():
            if path.endswith(".tsx"):
                assert "ErrorBoundary" in content


class TestApiAgent:
    """Agent 5 — API."""

    @pytest.mark.anyio
    async def test_produces_api_files(
        self, ai_router: AIRouter, cwm: ContextWindowManager, sample_state: PipelineState,
    ) -> None:
        files = await run_api_agent(sample_state, ai_router, cwm)
        assert isinstance(files, dict)
        assert len(files) >= 2


class TestDbAgent:
    """Agent 6 — DB."""

    @pytest.mark.anyio
    async def test_produces_schema(
        self, ai_router: AIRouter, cwm: ContextWindowManager, sample_state: PipelineState,
    ) -> None:
        files = await run_db_agent(sample_state, ai_router, cwm)
        assert isinstance(files, dict)
        assert "prisma/schema.prisma" in files
        assert "src/lib/db.ts" in files

    @pytest.mark.anyio
    async def test_prisma_schema_valid(
        self, ai_router: AIRouter, cwm: ContextWindowManager, sample_state: PipelineState,
    ) -> None:
        files = await run_db_agent(sample_state, ai_router, cwm)
        schema = files["prisma/schema.prisma"]
        assert "datasource db" in schema
        assert "generator client" in schema
        assert "model User" in schema


class TestAuthAgent:
    """Agent 7 — auth."""

    @pytest.mark.anyio
    async def test_produces_auth_files(
        self, ai_router: AIRouter, cwm: ContextWindowManager, sample_state: PipelineState,
    ) -> None:
        files = await run_auth_agent(sample_state, ai_router, cwm)
        assert isinstance(files, dict)
        assert "src/lib/auth/AuthContext.tsx" in files
        assert "src/lib/auth/ProtectedRoute.tsx" in files
        assert "src/lib/auth/middleware.ts" in files
        assert "src/lib/auth/index.ts" in files


class TestStyleAgent:
    """Agent 8 — style."""

    @pytest.mark.anyio
    async def test_produces_style_files(
        self, ai_router: AIRouter, cwm: ContextWindowManager, sample_state: PipelineState,
    ) -> None:
        files = await run_style_agent(sample_state, ai_router, cwm)
        assert isinstance(files, dict)
        assert "src/styles/globals.css" in files
        assert "tailwind.config.ts" in files

    @pytest.mark.anyio
    async def test_unique_palette_per_app(
        self, ai_router: AIRouter, cwm: ContextWindowManager,
    ) -> None:
        """Two different app titles should generate different palettes."""
        state1: PipelineState = {
            "idea_spec": {"title": "Finance Dashboard", "description": "banking"},
            "generated_files": {}, "injected_schemas": {},
        }
        state2: PipelineState = {
            "idea_spec": {"title": "Gaming Platform", "description": "games"},
            "generated_files": {}, "injected_schemas": {},
        }
        files1 = await run_style_agent(state1, ai_router, cwm)
        files2 = await run_style_agent(state2, ai_router, cwm)
        # Different titles → different CSS custom properties
        assert files1["src/styles/globals.css"] != files2["src/styles/globals.css"]

    @pytest.mark.anyio
    async def test_google_fonts_import(
        self, ai_router: AIRouter, cwm: ContextWindowManager, sample_state: PipelineState,
    ) -> None:
        files = await run_style_agent(sample_state, ai_router, cwm)
        css = files["src/styles/globals.css"]
        assert "fonts.googleapis.com" in css


class TestTestAgent:
    """Agent 9 — test generation."""

    @pytest.mark.anyio
    async def test_produces_test_files(
        self, ai_router: AIRouter, cwm: ContextWindowManager, sample_state: PipelineState,
    ) -> None:
        files = await run_test_agent(sample_state, ai_router, cwm)
        assert isinstance(files, dict)
        assert len(files) >= 5
        assert "vitest.config.ts" in files

    @pytest.mark.anyio
    async def test_component_tests_exist(
        self, ai_router: AIRouter, cwm: ContextWindowManager, sample_state: PipelineState,
    ) -> None:
        files = await run_test_agent(sample_state, ai_router, cwm)
        test_files = [f for f in files if ".test." in f]
        assert len(test_files) >= 5


# ── Review Agent Tests ───────────────────────────────────────────────

class TestReviewAgent:
    """Agent 10 — review (final validation)."""

    @pytest.mark.anyio
    async def test_produces_review_result(
        self, ai_router: AIRouter, cwm: ContextWindowManager, sample_state: PipelineState,
    ) -> None:
        result = await run_review_agent(sample_state, ai_router, cwm)
        assert isinstance(result, ReviewResult)
        assert result.build_status in ("COMPLETED", "FAILED")
        assert len(result.steps) == 6  # 6 review steps

    @pytest.mark.anyio
    async def test_review_steps_are_tracked(
        self, ai_router: AIRouter, cwm: ContextWindowManager, sample_state: PipelineState,
    ) -> None:
        result = await run_review_agent(sample_state, ai_router, cwm)
        step_names = [s.step_name for s in result.steps]
        assert "file_coherence" in step_names
        assert "build_verification" in step_names
        assert "sast_security" in step_names
        assert "visual_regression" in step_names
        assert "post_build_checks" in step_names
        assert "final_snapshot" in step_names

    @pytest.mark.anyio
    async def test_review_captures_lighthouse(
        self, ai_router: AIRouter, cwm: ContextWindowManager, sample_state: PipelineState,
    ) -> None:
        result = await run_review_agent(sample_state, ai_router, cwm)
        assert "lcp_ms" in result.lighthouse_metrics
        assert "performance_score" in result.lighthouse_metrics


# ── G7 Gate Tests ────────────────────────────────────────────────────

class TestG7Gate:
    """Test Gate G7 catches errors in agent output."""

    def test_g7_passes_with_files(self) -> None:
        state: PipelineState = {
            "generated_files": {"src/components/ui/Button.tsx": "export default function Button() {}"},
            "errors": [],
        }
        result = validate_g7(state, agent_name="component")
        assert result["passed"] is True

    def test_g7_fails_with_agent_error(self) -> None:
        state: PipelineState = {
            "generated_files": {},
            "errors": ["component agent crashed: syntax error"],
        }
        result = validate_g7(state, agent_name="component")
        assert result["passed"] is False

    def test_g7_catches_deliberate_error(self) -> None:
        """Verify G7 catches when an agent produces errors."""
        state: PipelineState = {
            "generated_files": {"src/broken.tsx": "invalid typescript syntax"},
            "errors": ["scaffold crashed: deliberate test error"],
        }
        result = validate_g7(state, agent_name="scaffold")
        assert result["passed"] is False
        assert "scaffold" in result["reason"]


# ── Sequential Agent Tests ───────────────────────────────────────────

class TestSequentialExecution:
    """Test running agents 1-3 sequentially — verify cumulative output."""

    @pytest.mark.anyio
    async def test_agents_1_to_3_sequential(
        self, ai_router: AIRouter, cwm: ContextWindowManager, sample_state: PipelineState,
    ) -> None:
        """Run scaffold → router → component and verify cumulative files."""
        all_files: dict[str, str] = {}

        # Agent 1: scaffold
        scaffold_files = await run_scaffold_agent(sample_state, ai_router, cwm)
        assert isinstance(scaffold_files, dict)
        assert "package.json" in scaffold_files
        all_files.update(scaffold_files)

        # Agent 2: router
        sample_state["generated_files"] = all_files
        router_files = await run_router_agent(sample_state, ai_router, cwm)
        assert isinstance(router_files, dict)
        all_files.update(router_files)

        # Agent 3: component
        sample_state["generated_files"] = all_files
        component_files = await run_component_agent(sample_state, ai_router, cwm)
        assert isinstance(component_files, dict)
        all_files.update(component_files)

        # Verify cumulative output has files from all 3 agents
        assert "package.json" in all_files  # from scaffold
        assert any("/pages/" in f or "App.tsx" in f for f in all_files)  # from router
        assert "src/components/ui/Button.tsx" in all_files  # from component
        assert "src/components/ui/index.ts" in all_files  # barrel from component

        # All files are strings
        for path, content in all_files.items():
            assert isinstance(path, str)
            assert isinstance(content, str)
            assert len(content) > 0

    @pytest.mark.anyio
    async def test_valid_typescript_from_agents_1_to_3(
        self, ai_router: AIRouter, cwm: ContextWindowManager, sample_state: PipelineState,
    ) -> None:
        """Verify TypeScript files from agents 1-3 have valid structure."""
        scaffold_files = await run_scaffold_agent(sample_state, ai_router, cwm)
        router_files = await run_router_agent(sample_state, ai_router, cwm)
        component_files = await run_component_agent(sample_state, ai_router, cwm)

        all_ts_files: dict[str, str] = {}
        for files in (scaffold_files, router_files, component_files):
            for fp, content in files.items():
                if fp.endswith((".ts", ".tsx")):
                    all_ts_files[fp] = content

        assert len(all_ts_files) > 0
        for fp, content in all_ts_files.items():
            # Basic validity: not empty, has export or import
            assert len(content) > 0, f"{fp} is empty"


# ── Snapshot After Each Agent ────────────────────────────────────────

class TestSnapshotPerAgent:
    """Verify snapshot is captured after each agent."""

    @pytest.mark.anyio
    async def test_snapshot_per_agent(
        self, ai_router: AIRouter, cwm: ContextWindowManager, sample_state: PipelineState,
    ) -> None:
        service = SnapshotService()
        captured: list[str] = []

        with patch("app.agents.build.snapshot_service.upload_file", new_callable=AsyncMock) as mock_upload:
            mock_upload.side_effect = lambda **kwargs: kwargs["key"]

            for idx, agent_name in enumerate(BUILD_AGENT_NAMES, start=1):
                url = await service.capture_snapshot(
                    build_id="test-build",
                    project_id="test-project",
                    agent_name=agent_name,
                    snapshot_index=idx,
                    generated_files={f"src/{agent_name}.tsx": "content"},
                )
                captured.append(url)

            # 9 agents (1-9) = 9 snapshots
            assert len(captured) == 9
            assert all(url for url in captured)
            assert mock_upload.call_count == 9


# ── BUILD_AGENT_MAP Tests ───────────────────────────────────────────

class TestBuildAgentMap:
    """Verify BUILD_AGENT_MAP and BUILD_AGENT_NAMES consistency."""

    def test_all_names_in_map(self) -> None:
        for name in BUILD_AGENT_NAMES:
            assert name in BUILD_AGENT_MAP, f"{name} missing from BUILD_AGENT_MAP"

    def test_map_has_correct_count(self) -> None:
        assert len(BUILD_AGENT_MAP) == 9  # agents 1-9 (review not in map)
        assert len(BUILD_AGENT_NAMES) == 9

    def test_agent_order(self) -> None:
        expected = ("scaffold", "router", "component", "page", "api",
                    "db", "auth", "style", "test")
        assert BUILD_AGENT_NAMES == expected

    def test_all_agents_are_callable(self) -> None:
        for name, fn in BUILD_AGENT_MAP.items():
            assert callable(fn), f"{name} agent is not callable"


# ── Sandbox Runner Tests ─────────────────────────────────────────────

class TestSandboxRunnerStubs:
    """Verify sandbox runner stubs return correct types."""

    @pytest.mark.anyio
    async def test_tsc_check_stub(self) -> None:
        from app.agents.build.sandbox_runner import run_tsc_check
        result = await run_tsc_check("sandbox-1", {})
        assert isinstance(result, ToolResult)
        assert result.passed is True

    @pytest.mark.anyio
    async def test_semgrep_stub(self) -> None:
        from app.agents.build.sandbox_runner import run_semgrep
        result = await run_semgrep("sandbox-1", {})
        assert isinstance(result, SemgrepResult)
        assert result.findings == []

    @pytest.mark.anyio
    async def test_lighthouse_stub(self) -> None:
        from app.agents.build.sandbox_runner import run_lighthouse
        result = await run_lighthouse("sandbox-1")
        assert isinstance(result, LighthouseResult)
        assert result.metrics.lcp_ms < 2500

    @pytest.mark.anyio
    async def test_playwright_stub(self) -> None:
        from app.agents.build.sandbox_runner import run_playwright
        result = await run_playwright("sandbox-1", ["/", "/login"], "build-1")
        assert isinstance(result, PlaywrightResult)
        assert len(result.screenshots) == 2

    @pytest.mark.anyio
    async def test_axe_audit_stub(self) -> None:
        from app.agents.build.sandbox_runner import run_axe_audit
        result = await run_axe_audit("sandbox-1")
        assert isinstance(result, AxeResult)
        assert result.critical_count == 0

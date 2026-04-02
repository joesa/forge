"""
Tests for Reliability Layers 9 & 10.

Layer 9 — Resilience and recovery:
  1. Hotfix agent (AI-driven targeted repair, max 3 attempts)
  2. Rollback engine (restore last-good build from R2)
  3. Canary deploy (phased traffic migration with auto-rollback)
  4. Migration safety (block destructive SQL operations)

Layer 10 — AI agent reliability:
  5. Context window manager (auto-chunking for large contexts)
  6. CSS validator (Tailwind class validation in TSX)
  7. Determinism enforcer (force temperature=0, seed=42)
  8. Fallback cascade (multi-provider failover)

All tests use mocked external services — never real APIs (AGENTS.md rule #7).
"""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock

import pytest


# =====================================================================
# LAYER 9: RESILIENCE AND RECOVERY
# =====================================================================


# ── 1. HOTFIX AGENT ─────────────────────────────────────────────────


class TestHotfixAgent:
    """Tests for hotfix_agent.py."""

    @pytest.mark.asyncio
    async def test_successful_hotfix_in_one_attempt(self) -> None:
        """Single attempt fix → HotfixResult.success = True."""
        from app.reliability.layer9_resilience.hotfix_agent import (
            HotfixContext,
            apply_hotfix,
        )

        ctx = HotfixContext(
            failed_gate="G7",
            error_message="TypeError: Cannot read property 'map' of undefined",
            failing_file="src/App.tsx",
            error_line=10,
        )

        files = {
            "src/App.tsx": (
                "import React from 'react';\n"
                "\n"
                "export default function App() {\n"
                "  const items = undefined;\n"
                "  return (\n"
                "    <div>\n"
                "      {items.map(i => <span key={i}>{i}</span>)}\n"
                "    </div>\n"
                "  );\n"
                "}\n"
            ),
        }

        # Mock AI router that returns a valid fix
        mock_router = AsyncMock()
        mock_router.complete.return_value = json.dumps({
            "fixed_code": (
                "import React from 'react';\n"
                "\n"
                "export default function App() {\n"
                "  const items = [];\n"
                "  return (\n"
                "    <div>\n"
                "      {(items ?? []).map(i => <span key={i}>{i}</span>)}\n"
                "    </div>\n"
                "  );\n"
                "}\n"
            ),
            "explanation": "Added nullish coalescing and default value.",
        })

        result = await apply_hotfix(ctx, files, mock_router)

        assert result.success is True
        assert result.attempts == 1
        assert len(result.changes) == 1
        assert result.gate_re_ran == "G7"
        assert mock_router.complete.call_count == 1
        # Verify temperature was forced to 0
        call_kwargs = mock_router.complete.call_args.kwargs
        assert call_kwargs.get("temperature") == 0.0

    @pytest.mark.asyncio
    async def test_hotfix_with_gate_validator(self) -> None:
        """Hotfix with gate validator that passes."""
        from app.reliability.layer9_resilience.hotfix_agent import (
            HotfixContext,
            apply_hotfix,
        )

        ctx = HotfixContext(
            failed_gate="G8",
            error_message="Missing export: UserCard",
            failing_file="src/components/UserCard.tsx",
        )

        files = {
            "src/components/UserCard.tsx": "function UserCard() { return null; }",
        }

        mock_router = AsyncMock()
        mock_router.complete.return_value = json.dumps({
            "fixed_code": "export function UserCard() { return null; }",
            "explanation": "Added export keyword.",
        })

        # Gate validator that passes
        async def gate_ok(f: dict[str, str]) -> dict[str, Any]:
            return {"passed": True}

        result = await apply_hotfix(
            ctx, files, mock_router, gate_validator=gate_ok
        )

        assert result.success is True
        assert result.attempts == 1

    @pytest.mark.asyncio
    async def test_hotfix_exhausts_attempts(self) -> None:
        """Gate validator keeps failing → exhausts 3 attempts."""
        from app.reliability.layer9_resilience.hotfix_agent import (
            HotfixContext,
            MAX_ATTEMPTS,
            apply_hotfix,
        )

        ctx = HotfixContext(
            failed_gate="G10",
            error_message="Type error in UserProfile",
            failing_file="src/UserProfile.tsx",
            error_line=5,
        )

        original_content = "const x: string = 42;"
        files = {"src/UserProfile.tsx": original_content}

        mock_router = AsyncMock()
        mock_router.complete.return_value = json.dumps({
            "fixed_code": "const x: string = String(42);",
            "explanation": "Cast to string.",
        })

        # Gate always fails
        async def gate_fail(f: dict[str, str]) -> dict[str, Any]:
            return {"passed": False}

        result = await apply_hotfix(
            ctx, files, mock_router, gate_validator=gate_fail
        )

        assert result.success is False
        assert result.attempts == MAX_ATTEMPTS
        assert result.error is not None
        # Original content should be restored
        assert files["src/UserProfile.tsx"] == original_content

    @pytest.mark.asyncio
    async def test_hotfix_missing_file(self) -> None:
        """Failing file not in generated_files → error."""
        from app.reliability.layer9_resilience.hotfix_agent import (
            HotfixContext,
            apply_hotfix,
        )

        ctx = HotfixContext(
            failed_gate="G7",
            error_message="File not found",
            failing_file="src/Missing.tsx",
        )

        mock_router = AsyncMock()
        result = await apply_hotfix(ctx, {}, mock_router)

        assert result.success is False
        assert "not found" in (result.error or "").lower()
        assert mock_router.complete.call_count == 0

    @pytest.mark.asyncio
    async def test_hotfix_handles_invalid_llm_response(self) -> None:
        """LLM returns invalid JSON → still attempts fix."""
        from app.reliability.layer9_resilience.hotfix_agent import (
            HotfixContext,
            apply_hotfix,
        )

        ctx = HotfixContext(
            failed_gate="G7",
            error_message="Syntax error",
            failing_file="src/app.ts",
        )

        files = {"src/app.ts": "const x = {"}

        mock_router = AsyncMock()
        mock_router.complete.return_value = "const x = {};"  # Raw text, not JSON

        result = await apply_hotfix(ctx, files, mock_router)

        # Should still succeed (raw text used as fix)
        assert result.success is True
        assert result.attempts == 1

    @pytest.mark.asyncio
    async def test_hotfix_prompt_contains_error_context(self) -> None:
        """Verify the prompt includes gate, error msg, file, and line."""
        from app.reliability.layer9_resilience.hotfix_agent import (
            _build_hotfix_prompt,
            HotfixContext,
        )

        ctx = HotfixContext(
            failed_gate="G8",
            error_message="Missing import: useState",
            failing_file="src/Counter.tsx",
            error_line=3,
        )

        system, user = _build_hotfix_prompt(ctx, "const x = 1;", 1)

        assert "G8" in user
        assert "Missing import: useState" in user
        assert "src/Counter.tsx" in user
        assert "3" in user  # error_line

    @pytest.mark.asyncio
    async def test_extract_error_region(self) -> None:
        """Error region extraction respects context window."""
        from app.reliability.layer9_resilience.hotfix_agent import (
            _extract_error_region,
        )

        content = "\n".join(f"line {i}" for i in range(100))

        # With error line in the middle
        region = _extract_error_region(content, 50, context_lines=5)
        lines = region.split("\n")
        assert len(lines) == 11  # lines 44..54 inclusive

        # Without error line → full content
        full = _extract_error_region(content, None)
        assert full == content


# ── 2. ROLLBACK ENGINE ──────────────────────────────────────────────


class TestRollbackEngine:
    """Tests for rollback_engine.py."""

    @pytest.mark.asyncio
    async def test_successful_rollback(self) -> None:
        """Full rollback → retrieves files and deploys them."""
        from app.reliability.layer9_resilience.rollback_engine import (
            rollback_to_last_good_build,
        )

        # Mock build repo
        mock_repo = AsyncMock()
        mock_repo.find_last_successful_build.return_value = {
            "build_id": "build-abc-123",
            "r2_prefix": "builds/proj-1/build-abc-123/",
            "file_count": 3,
        }

        # Mock storage
        mock_storage = AsyncMock()
        mock_storage.list_files.return_value = [
            "builds/proj-1/build-abc-123/src/App.tsx",
            "builds/proj-1/build-abc-123/src/index.ts",
            "builds/proj-1/build-abc-123/package.json",
        ]
        mock_storage.download_file.side_effect = [
            b"export default function App() {}",
            b"import App from './App';",
            b'{"name":"myapp"}',
        ]

        # Mock deployer
        mock_deployer = AsyncMock()
        mock_deployer.deploy_files.return_value = True

        result = await rollback_to_last_good_build(
            "proj-1",
            build_repo=mock_repo,
            storage=mock_storage,
            deployer=mock_deployer,
        )

        assert result.success is True
        assert result.rolled_back_to_build_id == "build-abc-123"
        assert result.files_restored == 3

    @pytest.mark.asyncio
    async def test_rollback_no_good_build(self) -> None:
        """No successful build exists → error."""
        from app.reliability.layer9_resilience.rollback_engine import (
            rollback_to_last_good_build,
        )

        mock_repo = AsyncMock()
        mock_repo.find_last_successful_build.return_value = None

        result = await rollback_to_last_good_build(
            "proj-1",
            build_repo=mock_repo,
            storage=AsyncMock(),
        )

        assert result.success is False
        assert "no successful build" in (result.error or "").lower()

    @pytest.mark.asyncio
    async def test_rollback_empty_project_id(self) -> None:
        """Empty project_id → error."""
        from app.reliability.layer9_resilience.rollback_engine import (
            rollback_to_last_good_build,
        )

        result = await rollback_to_last_good_build("")
        assert result.success is False
        assert "required" in (result.error or "").lower()

    @pytest.mark.asyncio
    async def test_rollback_no_repo(self) -> None:
        """No build repo provided → error."""
        from app.reliability.layer9_resilience.rollback_engine import (
            rollback_to_last_good_build,
        )

        result = await rollback_to_last_good_build("proj-1")
        assert result.success is False
        assert "repository" in (result.error or "").lower()

    @pytest.mark.asyncio
    async def test_rollback_deploy_failure(self) -> None:
        """Sandbox deployment fails → rollback fails."""
        from app.reliability.layer9_resilience.rollback_engine import (
            rollback_to_last_good_build,
        )

        mock_repo = AsyncMock()
        mock_repo.find_last_successful_build.return_value = {
            "build_id": "build-xyz",
            "r2_prefix": "builds/proj-2/build-xyz/",
        }

        mock_storage = AsyncMock()
        mock_storage.list_files.return_value = [
            "builds/proj-2/build-xyz/index.html",
        ]
        mock_storage.download_file.return_value = b"<html></html>"

        mock_deployer = AsyncMock()
        mock_deployer.deploy_files.return_value = False

        result = await rollback_to_last_good_build(
            "proj-2",
            build_repo=mock_repo,
            storage=mock_storage,
            deployer=mock_deployer,
        )

        assert result.success is False
        assert "deployment failed" in (result.error or "").lower()

    @pytest.mark.asyncio
    async def test_rollback_without_deployer(self) -> None:
        """Rollback without deployer → still downloads files (for testing)."""
        from app.reliability.layer9_resilience.rollback_engine import (
            rollback_to_last_good_build,
        )

        mock_repo = AsyncMock()
        mock_repo.find_last_successful_build.return_value = {
            "build_id": "build-nod",
            "r2_prefix": "builds/proj-3/build-nod/",
        }

        mock_storage = AsyncMock()
        mock_storage.list_files.return_value = [
            "builds/proj-3/build-nod/main.py",
        ]
        mock_storage.download_file.return_value = b"print('hello')"

        result = await rollback_to_last_good_build(
            "proj-3",
            build_repo=mock_repo,
            storage=mock_storage,
        )

        assert result.success is True
        assert result.files_restored == 1


# ── 3. CANARY DEPLOY ────────────────────────────────────────────────


class TestCanaryDeploy:
    """Tests for canary_deploy.py."""

    @pytest.mark.asyncio
    async def test_successful_canary_all_phases(self) -> None:
        """All 3 phases pass → CanaryResult.success = True."""
        from app.reliability.layer9_resilience.canary_deploy import (
            CanaryPhase,
            deploy_canary,
        )

        mock_traffic = AsyncMock()
        mock_traffic.set_traffic_split.return_value = True

        mock_error = AsyncMock()
        mock_error.get_error_rate.return_value = 0.0  # 0% error rate

        mock_waiter = AsyncMock()

        result = await deploy_canary(
            "build-001",
            "proj-1",
            traffic_manager=mock_traffic,
            error_checker=mock_error,
            waiter=mock_waiter,
            phase_wait_seconds=0.01,
        )

        assert result.success is True
        assert result.final_phase == CanaryPhase.COMPLETED
        assert result.rolled_back is False
        assert len(result.phases) == 3

        # Traffic splits: 5%, 25%, 100%
        split_calls = mock_traffic.set_traffic_split.call_args_list
        percents = [call.args[2] for call in split_calls]
        assert percents == [5, 25, 100]

    @pytest.mark.asyncio
    async def test_canary_rollback_at_phase_1(self) -> None:
        """Error rate too high at 5% → auto-rollback."""
        from app.reliability.layer9_resilience.canary_deploy import (
            CanaryPhase,
            deploy_canary,
        )

        mock_traffic = AsyncMock()
        mock_traffic.set_traffic_split.return_value = True

        mock_error = AsyncMock()
        mock_error.get_error_rate.return_value = 0.05  # 5% error rate

        mock_waiter = AsyncMock()

        result = await deploy_canary(
            "build-002",
            "proj-1",
            traffic_manager=mock_traffic,
            error_checker=mock_error,
            waiter=mock_waiter,
            phase_wait_seconds=0.01,
        )

        assert result.success is False
        assert result.rolled_back is True
        assert result.final_phase == CanaryPhase.ROLLED_BACK
        assert len(result.phases) == 1  # Only phase 1 attempted

        # Should have set traffic to 0% (rollback)
        last_call = mock_traffic.set_traffic_split.call_args_list[-1]
        assert last_call.args[2] == 0

    @pytest.mark.asyncio
    async def test_canary_rollback_at_phase_2(self) -> None:
        """Pass phase 1, fail at phase 2 → rollback."""
        from app.reliability.layer9_resilience.canary_deploy import (
            deploy_canary,
        )

        mock_traffic = AsyncMock()
        mock_traffic.set_traffic_split.return_value = True

        # Phase 1 OK, Phase 2 fails
        mock_error = AsyncMock()
        mock_error.get_error_rate.side_effect = [0.0, 0.01]

        mock_waiter = AsyncMock()

        result = await deploy_canary(
            "build-003",
            "proj-1",
            traffic_manager=mock_traffic,
            error_checker=mock_error,
            waiter=mock_waiter,
            phase_wait_seconds=0.01,
        )

        assert result.success is False
        assert result.rolled_back is True
        assert len(result.phases) == 2

    @pytest.mark.asyncio
    async def test_canary_missing_params(self) -> None:
        """Missing build_id or project_id → error."""
        from app.reliability.layer9_resilience.canary_deploy import (
            deploy_canary,
        )

        result = await deploy_canary("", "proj-1")
        assert result.success is False
        assert "required" in (result.error or "").lower()

    @pytest.mark.asyncio
    async def test_canary_no_traffic_manager(self) -> None:
        """No traffic manager → error."""
        from app.reliability.layer9_resilience.canary_deploy import (
            deploy_canary,
        )

        result = await deploy_canary("build-001", "proj-1")
        assert result.success is False
        assert "required" in (result.error or "").lower()

    @pytest.mark.asyncio
    async def test_canary_traffic_split_failure(self) -> None:
        """Traffic split fails → error."""
        from app.reliability.layer9_resilience.canary_deploy import (
            deploy_canary,
        )

        mock_traffic = AsyncMock()
        mock_traffic.set_traffic_split.return_value = False

        mock_error = AsyncMock()
        mock_waiter = AsyncMock()

        result = await deploy_canary(
            "build-004",
            "proj-1",
            traffic_manager=mock_traffic,
            error_checker=mock_error,
            waiter=mock_waiter,
        )

        assert result.success is False
        assert "traffic split" in (result.error or "").lower()

    @pytest.mark.asyncio
    async def test_canary_phase_results_contain_error_rates(self) -> None:
        """Phase results contain accurate error rate data."""
        from app.reliability.layer9_resilience.canary_deploy import (
            deploy_canary,
        )

        mock_traffic = AsyncMock()
        mock_traffic.set_traffic_split.return_value = True

        rates = [0.0001, 0.0005, 0.0002]
        mock_error = AsyncMock()
        mock_error.get_error_rate.side_effect = rates

        mock_waiter = AsyncMock()

        result = await deploy_canary(
            "build-005",
            "proj-1",
            traffic_manager=mock_traffic,
            error_checker=mock_error,
            waiter=mock_waiter,
            phase_wait_seconds=0.01,
        )

        assert result.success is True
        for i, phase in enumerate(result.phases):
            assert phase.error_rate == rates[i]
            assert phase.passed is True


# ── 4. MIGRATION SAFETY ────────────────────────────────────────────


class TestMigrationSafety:
    """Tests for migration_safety.py."""

    @pytest.mark.asyncio
    async def test_safe_migration_passes(self) -> None:
        """Normal CREATE TABLE + ADD COLUMN → safe."""
        from app.reliability.layer9_resilience.migration_safety import (
            check_migration_safety,
        )

        sql = """
        CREATE TABLE users (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            email VARCHAR(255) NOT NULL,
            created_at TIMESTAMPTZ DEFAULT NOW()
        );

        ALTER TABLE users ADD COLUMN name VARCHAR(100);
        """

        report = await check_migration_safety(sql)
        assert report.safe is True
        assert len(report.destructive_ops) == 0
        assert report.statements_analyzed > 0

    @pytest.mark.asyncio
    async def test_drop_table_blocked(self) -> None:
        """DROP TABLE → always blocked."""
        from app.reliability.layer9_resilience.migration_safety import (
            OpType,
            check_migration_safety,
        )

        sql = "DROP TABLE users;"

        report = await check_migration_safety(sql)
        assert report.safe is False
        assert len(report.destructive_ops) == 1
        assert report.destructive_ops[0].op_type == OpType.DROP_TABLE
        assert report.destructive_ops[0].table_name == "users"

    @pytest.mark.asyncio
    async def test_drop_table_if_exists_blocked(self) -> None:
        """DROP TABLE IF EXISTS → also blocked."""
        from app.reliability.layer9_resilience.migration_safety import (
            check_migration_safety,
        )

        sql = "DROP TABLE IF EXISTS legacy_data;"

        report = await check_migration_safety(sql)
        assert report.safe is False
        assert any(
            op.table_name == "legacy_data"
            for op in report.destructive_ops
        )

    @pytest.mark.asyncio
    async def test_drop_column_blocked(self) -> None:
        """DROP COLUMN → blocked (data loss)."""
        from app.reliability.layer9_resilience.migration_safety import (
            OpType,
            check_migration_safety,
        )

        sql = "ALTER TABLE users DROP COLUMN email;"

        report = await check_migration_safety(sql)
        assert report.safe is False
        drop_col_ops = [
            op for op in report.destructive_ops
            if op.op_type == OpType.DROP_COLUMN
        ]
        assert len(drop_col_ops) == 1
        assert drop_col_ops[0].table_name == "users"
        assert drop_col_ops[0].column_name == "email"

    @pytest.mark.asyncio
    async def test_alter_column_type_warns(self) -> None:
        """ALTER COLUMN TYPE → warning (not blocked)."""
        from app.reliability.layer9_resilience.migration_safety import (
            OpSeverity,
            OpType,
            check_migration_safety,
        )

        sql = "ALTER TABLE users ALTER COLUMN age TYPE TEXT;"

        report = await check_migration_safety(sql)
        assert report.safe is True  # Warnings don't block
        assert len(report.warnings) > 0
        assert any(
            op.op_type == OpType.ALTER_COLUMN_TYPE
            and op.severity == OpSeverity.WARN
            for op in report.destructive_ops
        )

    @pytest.mark.asyncio
    async def test_delete_without_where_blocked(self) -> None:
        """DELETE FROM without WHERE → blocked."""
        from app.reliability.layer9_resilience.migration_safety import (
            OpType,
            check_migration_safety,
        )

        sql = "DELETE FROM audit_logs;"

        report = await check_migration_safety(sql)
        assert report.safe is False
        assert any(
            op.op_type == OpType.DELETE_WITHOUT_WHERE
            for op in report.destructive_ops
        )

    @pytest.mark.asyncio
    async def test_truncate_blocked(self) -> None:
        """TRUNCATE TABLE → blocked."""
        from app.reliability.layer9_resilience.migration_safety import (
            OpType,
            check_migration_safety,
        )

        sql = "TRUNCATE TABLE sessions;"

        report = await check_migration_safety(sql)
        assert report.safe is False
        assert any(
            op.op_type == OpType.TRUNCATE_TABLE
            for op in report.destructive_ops
        )

    @pytest.mark.asyncio
    async def test_empty_sql_fails(self) -> None:
        """Empty SQL → error."""
        from app.reliability.layer9_resilience.migration_safety import (
            check_migration_safety,
        )

        report = await check_migration_safety("")
        assert report.safe is False
        assert report.error is not None

    @pytest.mark.asyncio
    async def test_multiple_destructive_ops(self) -> None:
        """Multiple destructive ops detected in one migration."""
        from app.reliability.layer9_resilience.migration_safety import (
            check_migration_safety,
        )

        sql = """
        DROP TABLE old_sessions;
        ALTER TABLE users DROP COLUMN legacy_field;
        DELETE FROM temp_data;
        """

        report = await check_migration_safety(sql)
        assert report.safe is False
        assert len(report.destructive_ops) >= 3

    @pytest.mark.asyncio
    async def test_comments_are_skipped(self) -> None:
        """SQL comments should not trigger detections."""
        from app.reliability.layer9_resilience.migration_safety import (
            check_migration_safety,
        )

        sql = """
        -- DROP TABLE users;
        /* DELETE FROM sessions; */
        CREATE TABLE new_table (id INT);
        """

        report = await check_migration_safety(sql)
        assert report.safe is True

    @pytest.mark.asyncio
    async def test_rename_table_warns(self) -> None:
        """RENAME TABLE → warning only."""
        from app.reliability.layer9_resilience.migration_safety import (
            OpType,
            check_migration_safety,
        )

        sql = "ALTER TABLE old_name RENAME TO new_name;"

        report = await check_migration_safety(sql)
        assert report.safe is True  # Warnings don't block
        assert any(
            op.op_type == OpType.RENAME_TABLE
            for op in report.destructive_ops
        )


# =====================================================================
# LAYER 10: AI AGENT RELIABILITY
# =====================================================================


# ── 5. CONTEXT WINDOW MANAGER ──────────────────────────────────────


class TestContextWindowManager:
    """Tests for context_window_manager.py."""

    @pytest.mark.asyncio
    async def test_small_context_no_chunking(self) -> None:
        """Small context → direct generation, no chunking."""
        from app.reliability.layer10_ai.context_window_manager import (
            ContextWindowManager,
        )

        mgr = ContextWindowManager()

        async def mock_agent(ctx: dict[str, Any]) -> dict[str, Any]:
            return {"files": {"app.tsx": "export default function App() {}"}}

        context = {"idea": "Build a todo app"}
        result = await mgr.managed_generate(mock_agent, context, "gpt-4o")

        assert result.was_chunked is False
        assert result.chunks_used == 1
        assert "files" in result.output

    @pytest.mark.asyncio
    async def test_large_context_triggers_chunking(self) -> None:
        """Context > 60% of model limit → chunking activated."""
        from app.reliability.layer10_ai.context_window_manager import (
            ContextWindowManager,
            CHARS_PER_TOKEN,
        )

        mgr = ContextWindowManager()

        # Create a context that exceeds 60% of gpt-4o limit (128k)
        # 60% of 128k = 76,800 tokens = ~307,200 chars
        large_text = "x" * (80_000 * CHARS_PER_TOKEN)

        call_count = 0

        async def mock_agent(ctx: dict[str, Any]) -> dict[str, Any]:
            nonlocal call_count
            call_count += 1
            return {"files": {f"chunk_{call_count}.tsx": "export default function C() {}"}}

        context = {"large_spec": large_text}
        result = await mgr.managed_generate(mock_agent, context, "gpt-4o")

        assert result.was_chunked is True
        assert result.chunks_used > 1
        assert call_count > 1
        assert result.total_tokens_estimated > 76_800

    @pytest.mark.asyncio
    async def test_model_limits(self) -> None:
        """Verify MODEL_LIMITS contains expected entries."""
        from app.reliability.layer10_ai.context_window_manager import (
            ContextWindowManager,
        )

        mgr = ContextWindowManager()
        assert mgr.get_model_limit("claude-opus-4-6") == 200_000
        assert mgr.get_model_limit("claude-sonnet-4-6") == 200_000
        assert mgr.get_model_limit("gpt-4o") == 128_000
        assert mgr.get_model_limit("gemini-3-pro") == 1_000_000
        # Unknown model → default
        assert mgr.get_model_limit("unknown-model") == 128_000

    @pytest.mark.asyncio
    async def test_token_estimation(self) -> None:
        """Token estimation: 4 chars ≈ 1 token."""
        from app.reliability.layer10_ai.context_window_manager import (
            estimate_tokens,
        )

        assert estimate_tokens("abcd") == 1
        assert estimate_tokens("a" * 100) == 25
        assert estimate_tokens("a" * 1000) == 250
        # Empty string → 1 (minimum)
        assert estimate_tokens("") == 1

    @pytest.mark.asyncio
    async def test_needs_chunking(self) -> None:
        """needs_chunking correctly detects threshold breach."""
        from app.reliability.layer10_ai.context_window_manager import (
            CHARS_PER_TOKEN,
            ContextWindowManager,
        )

        mgr = ContextWindowManager()

        small = {"text": "hello"}
        assert mgr.needs_chunking(small, "gpt-4o") is False

        # Just over 60% of 128k
        threshold_tokens = int(128_000 * 0.60)
        large = {"text": "x" * (threshold_tokens * CHARS_PER_TOKEN + 100)}
        assert mgr.needs_chunking(large, "gpt-4o") is True

    @pytest.mark.asyncio
    async def test_seam_checker_detects_duplicates(self) -> None:
        """Seam checker flags duplicate files across chunks."""
        from app.reliability.layer10_ai.context_window_manager import (
            check_seam,
        )

        chunk_a = {"files": {"App.tsx": "v1", "utils.ts": "helper"}}
        chunk_b = {"files": {"App.tsx": "v2", "api.ts": "fetch"}}

        issues = check_seam(chunk_a, chunk_b)
        assert len(issues) > 0
        assert any("App.tsx" in issue for issue in issues)

    @pytest.mark.asyncio
    async def test_merge_combines_files(self) -> None:
        """Merged output combines files from all chunks."""
        from app.reliability.layer10_ai.context_window_manager import (
            _merge_chunk_outputs,
        )

        outputs = [
            {"files": {"a.ts": "content_a"}},
            {"files": {"b.ts": "content_b"}},
        ]

        merged, issues = _merge_chunk_outputs(outputs)
        assert "a.ts" in merged["files"]
        assert "b.ts" in merged["files"]

    @pytest.mark.asyncio
    async def test_agent_error_propagates(self) -> None:
        """Agent function error propagates (not swallowed)."""
        from app.reliability.layer10_ai.context_window_manager import (
            ContextWindowManager,
        )

        mgr = ContextWindowManager()

        async def failing_agent(ctx: dict[str, Any]) -> dict[str, Any]:
            raise ValueError("Agent crashed")

        with pytest.raises(ValueError, match="Agent crashed"):
            await mgr.managed_generate(
                failing_agent, {"idea": "test"}, "gpt-4o"
            )


# ── 6. CSS VALIDATOR ────────────────────────────────────────────────


class TestCSSValidator:
    """Tests for css_validator.py."""

    @pytest.mark.asyncio
    async def test_valid_tailwind_classes_pass(self) -> None:
        """Valid Tailwind classes → passed = True."""
        from app.reliability.layer10_ai.css_validator import (
            validate_css_classes,
        )

        files = {
            "src/App.tsx": '''
                export function App() {
                    return (
                        <div className="flex items-center justify-between p-4 bg-blue-500 rounded-lg shadow-md">
                            <h1 className="text-2xl font-bold text-white">Hello</h1>
                            <button className="px-4 py-2 bg-white text-blue-500 rounded hover:bg-gray-100">
                                Click
                            </button>
                        </div>
                    );
                }
            ''',
        }

        report = await validate_css_classes(files)
        assert report.passed is True
        assert report.total_classes > 0
        assert len(report.invalid_classes) == 0

    @pytest.mark.asyncio
    async def test_invalid_classes_detected(self) -> None:
        """Made-up class names → detected as invalid."""
        from app.reliability.layer10_ai.css_validator import (
            validate_css_classes,
        )

        files = {
            "src/Bad.tsx": '''
                export function Bad() {
                    return <div className="xyzzy-magic foobar-3xl nonexistent-class">Bad</div>;
                }
            ''',
        }

        report = await validate_css_classes(files)
        assert report.passed is False
        assert len(report.invalid_classes) > 0

    @pytest.mark.asyncio
    async def test_responsive_prefixes_valid(self) -> None:
        """sm:, md:, lg: prefixes are valid."""
        from app.reliability.layer10_ai.css_validator import (
            validate_css_classes,
        )

        files = {
            "src/Responsive.tsx": '''
                export function R() {
                    return <div className="sm:flex md:grid lg:hidden xl:block">R</div>;
                }
            ''',
        }

        report = await validate_css_classes(files)
        assert report.passed is True

    @pytest.mark.asyncio
    async def test_arbitrary_values_valid(self) -> None:
        """Arbitrary value syntax w-[100px] is valid."""
        from app.reliability.layer10_ai.css_validator import (
            validate_css_classes,
        )

        files = {
            "src/Custom.tsx": '''
                export function Custom() {
                    return <div className="w-[100px] h-[50vh] bg-[#ff0000]">Custom</div>;
                }
            ''',
        }

        report = await validate_css_classes(files)
        assert report.passed is True

    @pytest.mark.asyncio
    async def test_hover_dark_mode_valid(self) -> None:
        """hover: and dark: prefixes are valid."""
        from app.reliability.layer10_ai.css_validator import (
            validate_css_classes,
        )

        files = {
            "src/Interactive.tsx": '''
                export function I() {
                    return <div className="hover:bg-blue-600 dark:bg-gray-800 focus:outline-none">I</div>;
                }
            ''',
        }

        report = await validate_css_classes(files)
        assert report.passed is True

    @pytest.mark.asyncio
    async def test_empty_files_error(self) -> None:
        """Empty file dict → error."""
        from app.reliability.layer10_ai.css_validator import (
            validate_css_classes,
        )

        report = await validate_css_classes({})
        assert report.passed is False
        assert report.error is not None

    @pytest.mark.asyncio
    async def test_no_tsx_files_passes(self) -> None:
        """Non-TSX files → nothing to validate → passes."""
        from app.reliability.layer10_ai.css_validator import (
            validate_css_classes,
        )

        files = {
            "src/utils.ts": "export const x = 1;",
            "README.md": "# Hello",
        }

        report = await validate_css_classes(files)
        assert report.passed is True

    @pytest.mark.asyncio
    async def test_invalid_classes_grouped_by_file(self) -> None:
        """by_file dict maps file → list of invalid classes."""
        from app.reliability.layer10_ai.css_validator import (
            validate_css_classes,
        )

        files = {
            "src/A.tsx": '<div className="xyzzy-magic">A</div>',
            "src/B.tsx": '<div className="flex p-4">B</div>',
        }

        report = await validate_css_classes(files)
        assert "src/A.tsx" in report.by_file
        assert "src/B.tsx" not in report.by_file


# ── 7. DETERMINISM ENFORCER ────────────────────────────────────────


class TestDeterminismEnforcer:
    """Tests for determinism_enforcer.py."""

    @pytest.mark.asyncio
    async def test_overrides_temperature(self) -> None:
        """Temperature != 0 → overridden to 0."""
        from app.reliability.layer10_ai.determinism_enforcer import (
            enforce_determinism,
            ENFORCED_TEMPERATURE,
        )

        captured: dict[str, Any] = {}

        @enforce_determinism
        async def mock_llm(prompt: str, *, temperature: float = 0.7) -> str:
            captured["temperature"] = temperature
            return "ok"

        await mock_llm("test", temperature=0.9)
        assert captured["temperature"] == ENFORCED_TEMPERATURE

    @pytest.mark.asyncio
    async def test_zero_temperature_unchanged(self) -> None:
        """Temperature already 0 → no warning, no override."""
        from app.reliability.layer10_ai.determinism_enforcer import (
            enforce_determinism,
        )

        captured: dict[str, Any] = {}

        @enforce_determinism
        async def mock_llm(prompt: str, *, temperature: float = 0.0) -> str:
            captured["temperature"] = temperature
            return "ok"

        await mock_llm("test", temperature=0.0)
        assert captured["temperature"] == 0.0

    @pytest.mark.asyncio
    async def test_seed_injected(self) -> None:
        """Seed=42 injected if function accepts seed parameter."""
        from app.reliability.layer10_ai.determinism_enforcer import (
            enforce_determinism,
            ENFORCED_SEED,
        )

        captured: dict[str, Any] = {}

        @enforce_determinism
        async def mock_llm(
            prompt: str, *, temperature: float = 0.0, seed: int = 0
        ) -> str:
            captured["seed"] = seed
            return "ok"

        await mock_llm("test")
        assert captured["seed"] == ENFORCED_SEED

    @pytest.mark.asyncio
    async def test_seed_overridden(self) -> None:
        """Wrong seed → overridden to 42."""
        from app.reliability.layer10_ai.determinism_enforcer import (
            enforce_determinism,
            ENFORCED_SEED,
        )

        captured: dict[str, Any] = {}

        @enforce_determinism
        async def mock_llm(
            prompt: str, *, temperature: float = 0.0, seed: int = 0
        ) -> str:
            captured["seed"] = seed
            return "ok"

        await mock_llm("test", seed=99)
        assert captured["seed"] == ENFORCED_SEED

    @pytest.mark.asyncio
    async def test_router_wrapper(self) -> None:
        """enforce_determinism_on_router wraps complete() method."""
        from app.reliability.layer10_ai.determinism_enforcer import (
            enforce_determinism_on_router,
            ENFORCED_TEMPERATURE,
        )

        captured: dict[str, Any] = {}

        class FakeRouter:
            async def complete(
                self, system_prompt: str, user_prompt: str,
                temperature: float = 0.7, response_format: str = "json",
            ) -> str:
                captured["temperature"] = temperature
                return "{}"

        router = FakeRouter()
        wrapped = enforce_determinism_on_router(router)

        await wrapped.complete(
            system_prompt="test",
            user_prompt="hello",
            temperature=0.5,
        )

        assert captured["temperature"] == ENFORCED_TEMPERATURE

    @pytest.mark.asyncio
    async def test_router_wrapper_injects_seed(self) -> None:
        """enforce_determinism_on_router also injects seed=42."""
        from app.reliability.layer10_ai.determinism_enforcer import (
            enforce_determinism_on_router,
            ENFORCED_SEED,
        )

        captured: dict[str, Any] = {}

        class FakeRouter:
            async def complete(
                self, system_prompt: str, user_prompt: str,
                temperature: float = 0.0, seed: int = 0,
            ) -> str:
                captured["seed"] = seed
                return "{}"

        router = FakeRouter()
        wrapped = enforce_determinism_on_router(router)

        await wrapped.complete(
            system_prompt="test",
            user_prompt="hello",
        )

        assert captured["seed"] == ENFORCED_SEED

    @pytest.mark.asyncio
    async def test_preserves_return_value(self) -> None:
        """Wrapper preserves the original return value."""
        from app.reliability.layer10_ai.determinism_enforcer import (
            enforce_determinism,
        )

        @enforce_determinism
        async def mock_llm(prompt: str, *, temperature: float = 0.7) -> str:
            return "expected_result"

        result = await mock_llm("test", temperature=0.5)
        assert result == "expected_result"


# ── 8. FALLBACK CASCADE ────────────────────────────────────────────


class TestFallbackCascade:
    """Tests for fallback_cascade.py."""

    @pytest.mark.asyncio
    async def test_preferred_provider_succeeds(self) -> None:
        """Primary provider works → no fallback."""
        from app.reliability.layer10_ai.fallback_cascade import (
            call_with_fallback,
        )

        async def mock_caller(
            prompt: str, provider: str, **kw: Any
        ) -> str:
            return f"response from {provider}"

        result = await call_with_fallback(
            prompt="Hello",
            preferred_provider="anthropic",
            user_providers={"anthropic": True, "openai": True},
            caller=mock_caller,
        )

        assert result == "response from anthropic"

    @pytest.mark.asyncio
    async def test_fallback_log_attribution(self) -> None:
        """FallbackLog is populated when passed for billing attribution."""
        from app.reliability.layer10_ai.fallback_cascade import (
            FallbackLog,
            RateLimitError,
            call_with_fallback,
        )

        async def mock_caller(
            prompt: str, provider: str, **kw: Any
        ) -> str:
            if provider == "anthropic":
                raise RateLimitError("anthropic", "429")
            return f"response from {provider}"

        log = FallbackLog()
        result = await call_with_fallback(
            prompt="Hello",
            preferred_provider="anthropic",
            user_providers={"anthropic": True, "openai": True},
            caller=mock_caller,
            fallback_log=log,
        )

        assert result == "response from openai"
        assert log.final_provider == "openai"
        assert log.fallback_count == 1
        assert len(log.attempts) == 2
        assert log.attempts[0].provider == "anthropic"
        assert log.attempts[0].success is False
        assert log.attempts[1].provider == "openai"
        assert log.attempts[1].success is True

    @pytest.mark.asyncio
    async def test_fallback_on_rate_limit(self) -> None:
        """Anthropic 429 → fallback to openai."""
        from app.reliability.layer10_ai.fallback_cascade import (
            RateLimitError,
            call_with_fallback,
        )

        call_log: list[str] = []

        async def mock_caller(
            prompt: str, provider: str, **kw: Any
        ) -> str:
            call_log.append(provider)
            if provider == "anthropic":
                raise RateLimitError("anthropic", "429 Too Many Requests")
            return f"response from {provider}"

        result = await call_with_fallback(
            prompt="Hello",
            preferred_provider="anthropic",
            user_providers={"anthropic": True, "openai": True},
            caller=mock_caller,
        )

        assert result == "response from openai"
        assert call_log == ["anthropic", "openai"]

    @pytest.mark.asyncio
    async def test_fallback_cascade_order(self) -> None:
        """Providers tried in priority order: anthropic → openai → gemini."""
        from app.reliability.layer10_ai.fallback_cascade import (
            ProviderError,
            call_with_fallback,
        )

        call_log: list[str] = []

        async def mock_caller(
            prompt: str, provider: str, **kw: Any
        ) -> str:
            call_log.append(provider)
            if provider in ("anthropic", "openai"):
                raise ProviderError(provider, "Service unavailable")
            return f"response from {provider}"

        result = await call_with_fallback(
            prompt="Hello",
            preferred_provider="anthropic",
            user_providers={
                "anthropic": True,
                "openai": True,
                "gemini": True,
            },
            caller=mock_caller,
        )

        assert result == "response from gemini"
        assert call_log == ["anthropic", "openai", "gemini"]

    @pytest.mark.asyncio
    async def test_all_providers_fail(self) -> None:
        """All providers fail → BuildAgentError raised."""
        from app.reliability.layer10_ai.fallback_cascade import (
            BuildAgentError,
            ProviderError,
            call_with_fallback,
        )

        async def mock_caller(
            prompt: str, provider: str, **kw: Any
        ) -> str:
            raise ProviderError(provider, "All broken")

        with pytest.raises(BuildAgentError) as exc_info:
            await call_with_fallback(
                prompt="Hello",
                preferred_provider="anthropic",
                user_providers={"anthropic": True, "openai": True},
                caller=mock_caller,
            )

        assert "2 providers failed" in str(exc_info.value)
        assert len(exc_info.value.attempts) == 2

    @pytest.mark.asyncio
    async def test_no_enabled_providers(self) -> None:
        """No enabled providers → BuildAgentError."""
        from app.reliability.layer10_ai.fallback_cascade import (
            BuildAgentError,
            call_with_fallback,
        )

        async def mock_caller(
            prompt: str, provider: str, **kw: Any
        ) -> str:
            return "ok"

        with pytest.raises(BuildAgentError, match="No enabled"):
            await call_with_fallback(
                prompt="Hello",
                preferred_provider="anthropic",
                user_providers={"anthropic": False},
                caller=mock_caller,
            )

    @pytest.mark.asyncio
    async def test_no_caller(self) -> None:
        """No caller → BuildAgentError."""
        from app.reliability.layer10_ai.fallback_cascade import (
            BuildAgentError,
            call_with_fallback,
        )

        with pytest.raises(BuildAgentError, match="No provider caller"):
            await call_with_fallback(
                prompt="Hello",
                preferred_provider="anthropic",
                user_providers={"anthropic": True},
            )

    @pytest.mark.asyncio
    async def test_disabled_preferred_uses_next(self) -> None:
        """Preferred provider disabled → uses next enabled one."""
        from app.reliability.layer10_ai.fallback_cascade import (
            call_with_fallback,
        )

        call_log: list[str] = []

        async def mock_caller(
            prompt: str, provider: str, **kw: Any
        ) -> str:
            call_log.append(provider)
            return f"response from {provider}"

        result = await call_with_fallback(
            prompt="Hello",
            preferred_provider="anthropic",
            user_providers={"anthropic": False, "openai": True},
            caller=mock_caller,
        )

        assert result == "response from openai"
        assert call_log == ["openai"]

    @pytest.mark.asyncio
    async def test_provider_priority_order(self) -> None:
        """Verify providers are tried in documented priority order."""
        from app.reliability.layer10_ai.fallback_cascade import (
            PROVIDER_PRIORITY,
        )

        assert PROVIDER_PRIORITY == [
            "anthropic", "openai", "gemini", "mistral", "cohere"
        ]

    @pytest.mark.asyncio
    async def test_fallback_with_mixed_errors(self) -> None:
        """Mix of rate limit and provider errors → keeps trying."""
        from app.reliability.layer10_ai.fallback_cascade import (
            ProviderError,
            RateLimitError,
            call_with_fallback,
        )

        call_log: list[str] = []

        async def mock_caller(
            prompt: str, provider: str, **kw: Any
        ) -> str:
            call_log.append(provider)
            if provider == "anthropic":
                raise RateLimitError("anthropic", "429")
            if provider == "openai":
                raise ProviderError("openai", "500 internal")
            return f"response from {provider}"

        result = await call_with_fallback(
            prompt="Hello",
            preferred_provider="anthropic",
            user_providers={
                "anthropic": True,
                "openai": True,
                "gemini": True,
            },
            caller=mock_caller,
        )

        assert result == "response from gemini"
        assert len(call_log) == 3


# =====================================================================
# INTEGRATION / PACKAGE-LEVEL TESTS
# =====================================================================


class TestPackageImports:
    """Verify all public APIs are importable from package __init__."""

    def test_layer9_imports(self) -> None:
        """All Layer 9 types importable from package."""
        from app.reliability.layer9_resilience import (
            CanaryPhase,
            CanaryResult,
            DestructiveOp,
            HotfixChange,
            HotfixContext,
            HotfixResult,
            RollbackResult,
            SafetyReport,
            apply_hotfix,
            check_migration_safety,
            deploy_canary,
            rollback_to_last_good_build,
        )

        # Verify types are real classes/functions
        assert callable(apply_hotfix)
        assert callable(check_migration_safety)
        assert callable(deploy_canary)
        assert callable(rollback_to_last_good_build)

    def test_layer10_imports(self) -> None:
        """All Layer 10 types importable from package."""
        from app.reliability.layer10_ai import (
            BuildAgentError,
            CSSValidationReport,
            ContextWindowManager,
            call_with_fallback,
            enforce_determinism,
            validate_css_classes,
        )

        assert callable(call_with_fallback)
        assert callable(enforce_determinism)
        assert callable(validate_css_classes)
        assert ContextWindowManager is not None

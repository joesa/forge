#!/usr/bin/env python3
"""
Standalone build agent test runner — no pytest dependency.
Run from backend/: python3 scripts/run_build_tests.py

Tests all 10 build agents WITHOUT pytest/conftest so we can
identify issues without the asyncio_mode=auto interference.
"""

import os
import sys
from pathlib import Path

# Add backend dir to Python path so 'app' is importable
_backend_dir = str(Path(__file__).resolve().parent.parent)
sys.path.insert(0, _backend_dir)
os.chdir(_backend_dir)
import json
import asyncio
import traceback
import time

# Force unbuffered output
sys.stdout = os.fdopen(sys.stdout.fileno(), 'w', buffering=1)

# Set env vars before any app imports
os.environ.setdefault("FORGE_ENV", "test")
os.environ.setdefault("FORGE_SECRET_KEY", "test-key")
os.environ.setdefault("FORGE_ENCRYPTION_KEY", "MDEyMzQ1Njc4OWFiY2RlZjAxMjM0NTY3ODlhYmNkZWY=")
os.environ.setdefault("FORGE_HMAC_SECRET", "test-hmac")
os.environ.setdefault("FORGE_FRONTEND_URL", "http://localhost:5173")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://x:x@localhost:5432/x")
os.environ.setdefault("DATABASE_READ_URL", "postgresql+asyncpg://x:x@localhost:5432/x")
os.environ.setdefault("NHOST_AUTH_URL", "https://x")
os.environ.setdefault("NHOST_ADMIN_SECRET", "x")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("SENTRY_DSN", "")
os.environ.setdefault("CLOUDFLARE_ACCOUNT_ID", "YOUR_CLOUDFLARE_ACCOUNT_ID")
os.environ.setdefault("R2_ACCESS_KEY_ID", "x")
os.environ.setdefault("R2_SECRET_ACCESS_KEY", "x")
os.environ.setdefault("R2_BUCKET_NAME", "forge-test")

# Mock R2 upload before importing agents
from unittest.mock import AsyncMock, MagicMock, patch
_upload_patch = patch("app.services.storage_service._build_client", return_value=MagicMock())
_upload_patch.start()

print("=" * 60)
print("FORGE Build Agent Test Runner")
print("=" * 60)

# ── Imports ──────────────────────────────────────────────────────
print("\nImporting build agents...", end=" ", flush=True)
from app.agents.ai_router import create_ai_router
from app.agents.build import (
    BUILD_AGENT_MAP, BUILD_AGENT_NAMES,
    ContextWindowManager, HotfixResult, ReviewResult, SnapshotService,
    run_scaffold_agent, run_router_agent, run_component_agent,
    run_page_agent, run_api_agent, run_db_agent, run_auth_agent,
    run_style_agent, run_test_agent, run_review_agent, run_hotfix_agent,
)
from app.agents.build.context_window_manager import (
    CHARS_PER_TOKEN, CHUNK_OVERLAP_TOKENS, DEFAULT_CONTEXT_LIMIT, SPLIT_THRESHOLD,
)
from app.agents.build.sandbox_runner import (
    ToolResult, SemgrepResult, LighthouseResult, PlaywrightResult, AxeResult,
    run_tsc_check, run_eslint, run_semgrep, run_playwright, run_lighthouse, run_axe_audit,
)
from app.agents.state import PipelineState
from app.agents.validators import validate_g7
print("OK")

# ── Test state ───────────────────────────────────────────────────
def make_state() -> dict:
    return {
        "pipeline_id": "test-pipeline-001",
        "project_id": "test-project-001",
        "user_id": "test-user-001",
        "current_stage": 6,
        "idea_spec": {
            "title": "Task Manager Pro",
            "description": "A powerful task management application",
            "features": ["kanban-board", "real-time-sync", "team-chat"],
            "framework": "react_vite",
            "target_audience": "small teams",
        },
        "comprehensive_plan": {
            "executive_summary": "Task management app with kanban",
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
                "react": "18.3.1", "react-dom": "18.3.1",
                "typescript": "5.4.5", "vite": "5.4.14", "tailwindcss": "3.4.17",
            },
            "lockfile_hash": "abc123", "conflicts_resolved": 0,
        },
        "env_contract": {
            "required": [{"name": "NODE_ENV", "type": "string", "description": "Env", "example": "production"}],
            "optional": [{"name": "VITE_API_URL", "type": "url", "description": "API", "example": "http://localhost:8000"}],
        },
        "injected_schemas": {}, "generated_files": {},
        "gate_results": {}, "errors": [],
        "build_manifest": {"files": [], "framework": "react_vite", "total_agents": 10},
    }

# ── Test runner ──────────────────────────────────────────────────
passed = 0
failed = 0
errors = []

def test(name: str, fn):
    global passed, failed
    sys.stdout.write(f"  {name}... ")
    sys.stdout.flush()
    t0 = time.time()
    try:
        fn()
        elapsed = time.time() - t0
        print(f"PASSED ({elapsed:.2f}s)")
        passed += 1
    except Exception as e:
        elapsed = time.time() - t0
        print(f"FAILED ({elapsed:.2f}s)")
        print(f"    Error: {e}")
        failed += 1
        errors.append((name, str(e)))

async def atest_run(name: str, coro_fn):
    global passed, failed
    sys.stdout.write(f"  {name}... ")
    sys.stdout.flush()
    t0 = time.time()
    try:
        await coro_fn()
        elapsed = time.time() - t0
        print(f"PASSED ({elapsed:.2f}s)")
        passed += 1
    except Exception as e:
        elapsed = time.time() - t0
        print(f"FAILED ({elapsed:.2f}s)")
        print(f"    Error: {e}")
        traceback.print_exc()
        failed += 1
        errors.append((name, str(e)))

# ── Sync Tests ───────────────────────────────────────────────────
print("\n── Context Window Manager ──")

def assert_eq(a, b):
    assert a == b, f"{a} != {b}"

def assert_true(cond, msg=""):
    assert cond, msg

router = create_ai_router(provider="stub")
cwm = ContextWindowManager(router)

test("token_estimation", lambda: assert_eq(cwm._estimate_tokens("a" * 400), 100))
test("no_split_under_threshold", lambda: assert_eq(len(cwm._split_prompt("short")), 1))

def test_split():
    small_cwm = ContextWindowManager(router, context_limit=100)
    chunks = small_cwm._split_prompt("x" * 500)
    assert len(chunks) > 1, f"Expected >1 chunks, got {len(chunks)}"
test("split_over_threshold", test_split)

def test_merge():
    r = cwm._merge_file_results([{"a": "1", "b": "2"}, {"c": "3", "b": "updated"}])
    assert r["b"] == "updated" and r["a"] == "1" and r["c"] == "3"
test("merge_file_results", test_merge)

test("parse_valid_json", lambda: assert_eq(cwm._parse_response('{"f.ts":"c"}', "t"), {"f.ts": "c"}))
test("parse_invalid_json", lambda: assert_eq(cwm._parse_response("nope", "t"), {}))
test("parse_non_dict", lambda: assert_eq(cwm._parse_response("[1]", "t"), {}))

print("\n── BUILD_AGENT_MAP ──")
test("all_names_in_map", lambda: [assert_eq(n in BUILD_AGENT_MAP, True) for n in BUILD_AGENT_NAMES])
test("map_count", lambda: assert_eq(len(BUILD_AGENT_MAP), 9))
test("names_count", lambda: assert_eq(len(BUILD_AGENT_NAMES), 9))
test("agent_order", lambda: assert_eq(BUILD_AGENT_NAMES,
    ("scaffold", "router", "component", "page", "api", "db", "auth", "style", "test")))

print("\n── G7 Gate ──")
def test_g7_pass():
    s = {"generated_files": {"src/Button.tsx": "code"}, "errors": []}
    assert validate_g7(s, agent_name="component")["passed"] is True
test("g7_passes_with_files", test_g7_pass)

def test_g7_fail():
    s = {"generated_files": {}, "errors": ["component crashed"]}
    assert validate_g7(s, agent_name="component")["passed"] is False
test("g7_fails_with_errors", test_g7_fail)

# ── Async Tests ──────────────────────────────────────────────────
async def run_async_tests():
    r = create_ai_router(provider="stub")
    c = ContextWindowManager(r)
    state = make_state()

    with patch("app.agents.build.snapshot_service.upload_file", new_callable=AsyncMock, return_value=None):
        print("\n── Agent 1: scaffold ──")
        await atest_run("produces_files", async_wrap(run_scaffold_agent, state, r, c,
            check=lambda f: assert_true(len(f) > 0 and "package.json" in f and "tsconfig.json" in f,
                f"Expected package.json+tsconfig.json, got {list(f.keys())[:5]}")))

        await atest_run("package_json_valid", async_wrap(run_scaffold_agent, state, r, c,
            check=lambda f: assert_true(json.loads(f["package.json"])["dependencies"]["react"] == "18.3.1", "react version")))

        await atest_run("gitignore_present", async_wrap(run_scaffold_agent, state, r, c,
            check=lambda f: assert_true(".gitignore" in f and "node_modules" in f[".gitignore"], ".gitignore")))

        print("\n── Agent 2: router ──")
        await atest_run("produces_routes", async_wrap(run_router_agent, state, r, c,
            check=lambda f: assert_true(len(f) >= 4 and "src/App.tsx" in f, f"got {len(f)} files")))

        print("\n── Agent 3: component ──")
        await atest_run("produces_components", async_wrap(run_component_agent, state, r, c,
            check=lambda f: assert_true(len(f) >= 14 and "src/components/ui/Button.tsx" in f, f"got {len(f)} files")))

        print("\n── Agent 4: page ──")
        await atest_run("produces_pages", async_wrap(run_page_agent, state, r, c,
            check=lambda f: assert_true(len(f) >= 4, f"got {len(f)} files")))

        print("\n── Agent 5: api ──")
        await atest_run("produces_api", async_wrap(run_api_agent, state, r, c,
            check=lambda f: assert_true(len(f) >= 2, f"got {len(f)} files")))

        print("\n── Agent 6: db ──")
        await atest_run("produces_schema", async_wrap(run_db_agent, state, r, c,
            check=lambda f: assert_true("prisma/schema.prisma" in f, f"got {list(f.keys())[:5]}")))

        print("\n── Agent 7: auth ──")
        await atest_run("produces_auth", async_wrap(run_auth_agent, state, r, c,
            check=lambda f: assert_true("src/lib/auth/AuthContext.tsx" in f, f"got {list(f.keys())[:5]}")))

        print("\n── Agent 8: style ──")
        await atest_run("produces_styles", async_wrap(run_style_agent, state, r, c,
            check=lambda f: assert_true("src/styles/globals.css" in f, f"got {list(f.keys())[:5]}")))

        print("\n── Agent 9: test ──")
        await atest_run("produces_tests", async_wrap(run_test_agent, state, r, c,
            check=lambda f: assert_true(len(f) >= 5 and "vitest.config.ts" in f, f"got {len(f)} files")))

        print("\n── Agent 10: review ──")
        await atest_run("produces_review", async_wrap_review(run_review_agent, state, r, c))

        print("\n── Hotfix agent ──")
        await atest_run("hotfix_not_implemented", async_wrap_hotfix(state, r, c))

        print("\n── Sandbox runner stubs ──")
        await atest_run("tsc_check", async_wrap_sandbox(run_tsc_check, "s1", {}, ToolResult))
        await atest_run("semgrep", async_wrap_sandbox(run_semgrep, "s1", {}, SemgrepResult))
        await atest_run("lighthouse", async_wrap_sandbox_simple(run_lighthouse, "s1", LighthouseResult))
        await atest_run("axe_audit", async_wrap_sandbox_simple(run_axe_audit, "s1", AxeResult))

        print("\n── Sequential agents 1-3 ──")
        await atest_run("agents_1_to_3_sequential", async_sequential(state, r, c))

        print("\n── Snapshot per agent ──")
        await atest_run("snapshot_per_agent", async_snapshot_test())


def assert_true(cond, msg=""):
    assert cond, msg

def async_wrap(agent_fn, state, r, c, check=None):
    async def inner():
        files = await agent_fn(state, r, c)
        assert isinstance(files, dict), f"Expected dict, got {type(files)}"
        if check:
            check(files)
    return inner

def async_wrap_review(agent_fn, state, r, c):
    async def inner():
        result = await agent_fn(state, r, c)
        assert isinstance(result, ReviewResult), f"Expected ReviewResult, got {type(result)}"
        assert result.build_status in ("COMPLETED", "FAILED")
        assert len(result.steps) == 6, f"Expected 6 steps, got {len(result.steps)}"
    return inner

def async_wrap_hotfix(state, r, c):
    async def inner():
        result = await run_hotfix_agent(
            state=state, ai_router=r, context_window_manager=c,
            failed_agent="component", error_details="test", generated_files={},
        )
        assert isinstance(result, HotfixResult)
        assert result.success is False
        assert result.reason == "not_yet_implemented"
    return inner

def async_wrap_sandbox(fn, sandbox_id, files, expected_type):
    async def inner():
        result = await fn(sandbox_id, files)
        assert isinstance(result, expected_type), f"Expected {expected_type}, got {type(result)}"
        assert result.passed is True
    return inner

def async_wrap_sandbox_simple(fn, sandbox_id, expected_type):
    async def inner():
        result = await fn(sandbox_id)
        assert isinstance(result, expected_type), f"Expected {expected_type}, got {type(result)}"
    return inner

def async_sequential(state, r, c):
    async def inner():
        all_files = {}
        s1 = await run_scaffold_agent(state, r, c)
        all_files.update(s1)
        assert "package.json" in all_files

        state["generated_files"] = all_files
        s2 = await run_router_agent(state, r, c)
        all_files.update(s2)

        state["generated_files"] = all_files
        s3 = await run_component_agent(state, r, c)
        all_files.update(s3)

        assert "src/components/ui/Button.tsx" in all_files
        assert any("/pages/" in f or "App.tsx" in f for f in all_files)
    return inner

def async_snapshot_test():
    async def inner():
        service = SnapshotService()
        with patch("app.agents.build.snapshot_service.upload_file",
                   new_callable=AsyncMock, side_effect=lambda **kw: kw["key"]):
            captured = []
            for idx, name in enumerate(BUILD_AGENT_NAMES, start=1):
                url = await service.capture_snapshot(
                    build_id="test", project_id="p1", agent_name=name,
                    snapshot_index=idx, generated_files={f"src/{name}.tsx": "content"},
                )
                captured.append(url)
            assert len(captured) == 9, f"Expected 9 snapshots, got {len(captured)}"
            assert all(url for url in captured)
    return inner

# ── Run ──────────────────────────────────────────────────────────
asyncio.run(run_async_tests())

print(f"\n{'='*60}")
print(f"Results: {passed} passed, {failed} failed")
if errors:
    print("\nFailed tests:")
    for name, err in errors:
        print(f"  ✗ {name}: {err}")
print(f"{'='*60}")
sys.exit(1 if failed else 0)

#!/usr/bin/env python3
"""
Diagnostic script — run from backend/: python3 scripts/debug_imports.py
Identifies exactly which import hangs in the build agent chain.
"""

import os
import sys
import time
from pathlib import Path

# Add backend dir to Python path so 'app' is importable
_backend_dir = str(Path(__file__).resolve().parent.parent)
sys.path.insert(0, _backend_dir)
os.chdir(_backend_dir)

# Force unbuffered output
sys.stdout = os.fdopen(sys.stdout.fileno(), 'w', buffering=1)

# Set minimal env vars so pydantic-settings doesn't fail
os.environ.setdefault("FORGE_ENV", "test")
os.environ.setdefault("FORGE_SECRET_KEY", "x")
os.environ.setdefault("FORGE_ENCRYPTION_KEY", "MDEyMzQ1Njc4OWFiY2RlZjAxMjM0NTY3ODlhYmNkZWY=")
os.environ.setdefault("FORGE_HMAC_SECRET", "x")
os.environ.setdefault("FORGE_FRONTEND_URL", "http://localhost:5173")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://x:x@localhost:5432/x")
os.environ.setdefault("DATABASE_READ_URL", "postgresql+asyncpg://x:x@localhost:5432/x")
os.environ.setdefault("NHOST_AUTH_URL", "https://x")
os.environ.setdefault("NHOST_ADMIN_SECRET", "x")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("SENTRY_DSN", "")
os.environ.setdefault("CLOUDFLARE_ACCOUNT_ID", "x")
os.environ.setdefault("R2_ACCESS_KEY_ID", "x")
os.environ.setdefault("R2_SECRET_ACCESS_KEY", "x")
os.environ.setdefault("R2_BUCKET_NAME", "x")

def timed_import(label, import_fn):
    sys.stdout.write(f"  {label}... ")
    sys.stdout.flush()
    t0 = time.time()
    try:
        result = import_fn()
        elapsed = time.time() - t0
        sys.stdout.write(f"OK ({elapsed:.2f}s)\n")
        return result
    except Exception as e:
        elapsed = time.time() - t0
        sys.stdout.write(f"FAILED ({elapsed:.2f}s): {e}\n")
        return None

print("=== FORGE Build Agent Import Diagnostics ===\n")

print("Step 1: Core imports")
timed_import("app.config", lambda: __import__("app.config"))
timed_import("app.core.redis", lambda: __import__("app.core.redis"))
timed_import("app.agents.state", lambda: __import__("app.agents.state"))
timed_import("app.agents.ai_router", lambda: __import__("app.agents.ai_router"))

print("\nStep 2: Build agent imports")
timed_import("app.agents.build.context_window_manager", lambda: __import__("app.agents.build.context_window_manager"))
timed_import("app.agents.build.snapshot_service", lambda: __import__("app.agents.build.snapshot_service"))
timed_import("app.agents.build.sandbox_runner", lambda: __import__("app.agents.build.sandbox_runner"))
timed_import("app.agents.build.hotfix_agent", lambda: __import__("app.agents.build.hotfix_agent"))
timed_import("app.agents.build.scaffold_agent", lambda: __import__("app.agents.build.scaffold_agent"))
timed_import("app.agents.build.router_agent", lambda: __import__("app.agents.build.router_agent"))
timed_import("app.agents.build.component_agent", lambda: __import__("app.agents.build.component_agent"))
timed_import("app.agents.build.review_agent", lambda: __import__("app.agents.build.review_agent"))
timed_import("app.agents.build (full)", lambda: __import__("app.agents.build"))

print("\nStep 3: Graph and pipeline")
timed_import("app.agents.graph", lambda: __import__("app.agents.graph"))
timed_import("app.agents.validators", lambda: __import__("app.agents.validators"))

print("\nStep 4: Reliability layers")
timed_import("app.reliability.layer4_coherence", lambda: __import__("app.reliability.layer4_coherence"))
timed_import("app.reliability.layer2_schema_driven", lambda: __import__("app.reliability.layer2_schema_driven"))
timed_import("app.reliability.layer1_pregeneration", lambda: __import__("app.reliability.layer1_pregeneration"))

print("\nStep 5: FastAPI app")
timed_import("app.api.v1.pipeline", lambda: __import__("app.api.v1.pipeline"))
timed_import("app.middleware.auth", lambda: __import__("app.middleware.auth"))
timed_import("app.middleware.rate_limit", lambda: __import__("app.middleware.rate_limit"))
timed_import("app.main", lambda: __import__("app.main"))

print("\nStep 6: Quick functional test")
import asyncio
from app.agents.ai_router import create_ai_router
from app.agents.build import BUILD_AGENT_NAMES, ContextWindowManager

router = create_ai_router(provider="stub")
cwm = ContextWindowManager(router)

# Sync test
chunks = cwm._split_prompt("x" * 500)
print(f"  CWM split: {len(chunks)} chunks")

# Async test
async def quick_test():
    from app.agents.build import run_scaffold_agent
    state = {
        "idea_spec": {"title": "Test", "description": "test", "features": [], "framework": "react_vite"},
        "comprehensive_plan": {},
        "resolved_dependencies": {"packages": {"react": "18.3.1"}, "lockfile_hash": "x"},
        "env_contract": {"required": [{"name": "NODE_ENV", "type": "string", "description": "x", "example": "prod"}], "optional": []},
        "generated_files": {}, "injected_schemas": {},
    }
    files = await run_scaffold_agent(state, router, cwm)
    print(f"  Scaffold agent: {len(files)} files generated")
    assert "package.json" in files
    print(f"  package.json present: YES")

asyncio.run(quick_test())

print("\n=== ALL DIAGNOSTICS PASSED ===")

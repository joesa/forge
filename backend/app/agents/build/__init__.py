# ruff: noqa: F401
"""
FORGE Build Agents — 10 sequential code-generation agents for Stage 6.

Agent order (sequential):
  1. scaffold_agent   — project scaffold (package.json, tsconfig, etc.)
  2. router_agent     — routes/pages skeleton
  3. component_agent  — shared UI components
  4. page_agent       — page components using shared components
  5. api_agent        — API route handlers
  6. db_agent         — database schema, models, migrations
  7. auth_agent       — authentication system
  8. style_agent      — CSS, theming, unique visual identity
  9. test_agent       — unit and integration tests
  10. review_agent    — final validation (does NOT generate app code)

All agents run at temperature=0, fixed seed (Architecture rule #4).
Context window manager handles prompt splitting.
Snapshot service captures state after each agent.
"""

from app.agents.build.scaffold_agent import run_scaffold_agent
from app.agents.build.router_agent import run_router_agent
from app.agents.build.component_agent import run_component_agent
from app.agents.build.page_agent import run_page_agent
from app.agents.build.api_agent import run_api_agent
from app.agents.build.db_agent import run_db_agent
from app.agents.build.auth_agent import run_auth_agent
from app.agents.build.style_agent import run_style_agent
from app.agents.build.test_agent import run_test_agent
from app.agents.build.review_agent import run_review_agent, ReviewResult

from app.agents.build.context_window_manager import ContextWindowManager
from app.agents.build.snapshot_service import SnapshotService
from app.agents.build.hotfix_agent import run_hotfix_agent, HotfixResult

# Agent name → run function mapping (agents 1-9, not review)
BUILD_AGENT_MAP: dict[str, object] = {
    "scaffold": run_scaffold_agent,
    "router": run_router_agent,
    "component": run_component_agent,
    "page": run_page_agent,
    "api": run_api_agent,
    "db": run_db_agent,
    "auth": run_auth_agent,
    "style": run_style_agent,
    "test": run_test_agent,
}

# Ordered agent names (execution order)
BUILD_AGENT_NAMES = (
    "scaffold", "router", "component", "page", "api",
    "db", "auth", "style", "test",
)

__all__ = [
    # Agent runners
    "run_scaffold_agent",
    "run_router_agent",
    "run_component_agent",
    "run_page_agent",
    "run_api_agent",
    "run_db_agent",
    "run_auth_agent",
    "run_style_agent",
    "run_test_agent",
    "run_review_agent",
    "run_hotfix_agent",
    # Result types
    "ReviewResult",
    "HotfixResult",
    # Utilities
    "ContextWindowManager",
    "SnapshotService",
    # Maps
    "BUILD_AGENT_MAP",
    "BUILD_AGENT_NAMES",
]

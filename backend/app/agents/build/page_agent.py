"""
Page Agent (Agent 4) — generates all page components using shared components.

Layer 2 inject: component prop types from agent 3.
Layer 6: ErrorBoundary wrapper injected around every page automatically.
Files: all pages in app/ or pages/ directory.
Gate G7 after.
"""

from __future__ import annotations

import time
from typing import Any

import structlog

from app.agents.ai_router import AIRouter
from app.agents.build.context_window_manager import ContextWindowManager
from app.agents.state import PipelineState

logger = structlog.get_logger(__name__)

AGENT_NAME = "page"

_SYSTEM_PROMPT = """You are a senior frontend engineer generating page components.
Each page should use shared UI components from @/components/ui.
Every page must be wrapped with ErrorBoundary for fault isolation.

Return a JSON object where keys are file paths and values are file contents.
Requirements:
- Import shared components: Button, Input, Card, Modal, etc.
- Use proper TypeScript types
- Include ErrorBoundary wrapper
- Handle loading and error states
- Responsive layout with Tailwind CSS"""


def _extract_pages(state: PipelineState) -> list[dict[str, str]]:
    """Extract page definitions from comprehensive plan or features."""
    plan = state.get("comprehensive_plan", {})
    pages: list[dict[str, str]] = []

    architect = plan.get("architect_output", {})
    if isinstance(architect, dict):
        page_list = architect.get("pages", architect.get("routes", []))
        if isinstance(page_list, list):
            for p in page_list:
                if isinstance(p, dict):
                    pages.append(p)
                elif isinstance(p, str):
                    name = p.strip("/").replace("/", "_") or "home"
                    pages.append({"path": p, "name": name})

    if not pages:
        idea = state.get("idea_spec", {})
        pages = [
            {"path": "/", "name": "home"},
            {"path": "/login", "name": "login"},
            {"path": "/register", "name": "register"},
            {"path": "/dashboard", "name": "dashboard"},
            {"path": "/settings", "name": "settings"},
        ]
        for feat in (idea.get("features", []) or []):
            if isinstance(feat, str):
                slug = feat.lower().replace(" ", "-")[:32]
                pages.append({"path": f"/{slug}", "name": slug.replace("-", "_")})

    return pages


def _build_default_pages(state: PipelineState) -> dict[str, str]:
    """Build deterministic default page components."""
    idea = state.get("idea_spec", {})
    title = str(idea.get("title", "App"))
    pages = _extract_pages(state)
    files: dict[str, str] = {}

    for page in pages:
        name = page.get("name", "page")
        comp = "".join(w.capitalize() for w in name.replace("-", "_").split("_")) + "Page"
        fp = f"src/pages/{name.replace('-', '_')}.tsx"

        is_dashboard = "dashboard" in name
        is_settings = "settings" in name
        is_auth = name in ("login", "register")

        if is_auth:
            content = (
                "import { Card, Button, Input } from '@/components/ui';\n"
                "import ErrorBoundary from '@/components/ui/ErrorBoundary';\n\n"
                f"export default function {comp}() {{\n"
                "  return (\n"
                "    <ErrorBoundary>\n"
                "      <div className=\"flex min-h-screen items-center justify-center\">\n"
                f"        <Card className=\"w-full max-w-md\">\n"
                f"          <h1 className=\"mb-6 text-2xl font-bold\">{name.replace('_', ' ').title()}</h1>\n"
                "          <form className=\"flex flex-col gap-4\">\n"
                "            <Input label=\"Email\" type=\"email\" placeholder=\"you@example.com\" />\n"
                "            <Input label=\"Password\" type=\"password\" placeholder=\"••••••••\" />\n"
                f"            <Button type=\"submit\">{name.replace('_', ' ').title()}</Button>\n"
                "          </form>\n"
                "        </Card>\n"
                "      </div>\n"
                "    </ErrorBoundary>\n"
                "  );\n"
                "}\n"
            )
        elif is_dashboard:
            content = (
                "import { Card, Badge, Spinner } from '@/components/ui';\n"
                "import ErrorBoundary from '@/components/ui/ErrorBoundary';\n\n"
                f"export default function {comp}() {{\n"
                "  return (\n"
                "    <ErrorBoundary>\n"
                "      <div className=\"p-6\">\n"
                f"        <h1 className=\"mb-6 text-2xl font-bold\">{title} Dashboard</h1>\n"
                "        <div className=\"grid grid-cols-1 gap-6 md:grid-cols-2 lg:grid-cols-3\">\n"
                "          <Card><h2 className=\"font-semibold\">Overview</h2><p className=\"text-gray-500\">Your activity</p></Card>\n"
                "          <Card><h2 className=\"font-semibold\">Stats</h2><Badge variant=\"success\">Active</Badge></Card>\n"
                "          <Card><h2 className=\"font-semibold\">Recent</h2><p className=\"text-gray-500\">Latest activity</p></Card>\n"
                "        </div>\n"
                "      </div>\n"
                "    </ErrorBoundary>\n"
                "  );\n"
                "}\n"
            )
        elif is_settings:
            content = (
                "import { Card, Button, Input, Divider } from '@/components/ui';\n"
                "import ErrorBoundary from '@/components/ui/ErrorBoundary';\n\n"
                f"export default function {comp}() {{\n"
                "  return (\n"
                "    <ErrorBoundary>\n"
                "      <div className=\"mx-auto max-w-2xl p-6\">\n"
                "        <h1 className=\"mb-6 text-2xl font-bold\">Settings</h1>\n"
                "        <Card>\n"
                "          <h2 className=\"mb-4 font-semibold\">Profile</h2>\n"
                "          <div className=\"flex flex-col gap-4\">\n"
                "            <Input label=\"Name\" placeholder=\"Your name\" />\n"
                "            <Input label=\"Email\" type=\"email\" placeholder=\"you@example.com\" />\n"
                "            <Divider />\n"
                "            <Button>Save Changes</Button>\n"
                "          </div>\n"
                "        </Card>\n"
                "      </div>\n"
                "    </ErrorBoundary>\n"
                "  );\n"
                "}\n"
            )
        else:
            content = (
                "import { Card } from '@/components/ui';\n"
                "import ErrorBoundary from '@/components/ui/ErrorBoundary';\n\n"
                f"export default function {comp}() {{\n"
                "  return (\n"
                "    <ErrorBoundary>\n"
                "      <div className=\"p-6\">\n"
                f"        <h1 className=\"mb-6 text-2xl font-bold\">{name.replace('_', ' ').title()}</h1>\n"
                "        <Card>\n"
                f"          <p>Welcome to {name.replace('_', ' ')}</p>\n"
                "        </Card>\n"
                "      </div>\n"
                "    </ErrorBoundary>\n"
                "  );\n"
                "}\n"
            )
        files[fp] = content

    return files


async def run_page_agent(
    state: PipelineState,
    ai_router: AIRouter,
    context_window_manager: ContextWindowManager,
) -> dict[str, str]:
    """Generate page components. temp=0, ErrorBoundary wrapping."""
    start = time.monotonic()
    idea = state.get("idea_spec", {})
    injected = state.get("injected_schemas", {})
    pages = _extract_pages(state)

    page_list = "\n".join(f"  - {p.get('path','/')} → {p.get('name','page')}" for p in pages)
    schema_ctx = ""
    for key in ("zod_schemas", "db_types"):
        if key in injected:
            schema_ctx += f"\n{key}:\n{str(injected[key])[:1500]}\n"

    user_prompt = (
        f"Project: {idea.get('title', 'Untitled')}\n"
        f"Pages:\n{page_list}\n{schema_ctx}"
    )

    try:
        files = await context_window_manager.generate(
            system_prompt=_SYSTEM_PROMPT, user_prompt=user_prompt, agent_name=AGENT_NAME,
        )
        if files:
            logger.info("page_agent.complete", elapsed_s=round(time.monotonic() - start, 3), files=len(files))
            return files
    except Exception as exc:
        logger.warning("page_agent.llm_fallback", error=str(exc))

    files = _build_default_pages(state)
    logger.info("page_agent.complete_default", elapsed_s=round(time.monotonic() - start, 3), files=len(files))
    return files

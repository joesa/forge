"""
Router Agent (Agent 2) — generates all routes/pages skeleton.

Layer 2 inject: full route list from comprehensive_plan's architect output.

Files generated:
  - app/layout.tsx
  - app/page.tsx
  - All route files as stubs

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

AGENT_NAME = "router"

_SYSTEM_PROMPT = """You are a senior frontend engineer generating the routing layer.
Generate all route/page files as TypeScript React components.

Return a JSON object where keys are file paths and values are file contents.
Example: {"app/layout.tsx": "...", "app/page.tsx": "...", "app/dashboard/page.tsx": "..."}

Requirements:
- app/layout.tsx: root layout with providers, metadata
- app/page.tsx: landing/home page
- Each route file: proper TypeScript, valid JSX, imports React
- Use React Router or Next.js App Router based on framework
- Every page component exports default
- Include proper TypeScript types for all props"""


def _extract_routes(state: PipelineState) -> list[dict[str, str]]:
    """Extract route definitions from the comprehensive plan."""
    plan = state.get("comprehensive_plan", {})
    routes: list[dict[str, str]] = []

    # Try different locations for route data
    architect_output = plan.get("architect_output", {})
    if isinstance(architect_output, dict):
        route_list = architect_output.get("routes", [])
        if isinstance(route_list, list):
            for r in route_list:
                if isinstance(r, dict):
                    routes.append(r)
                elif isinstance(r, str):
                    routes.append({"path": r, "name": r.strip("/").replace("/", "_") or "home"})

    # Fallback: extract from features
    if not routes:
        idea_spec = state.get("idea_spec", {})
        features = idea_spec.get("features", [])
        # Always include home
        routes.append({"path": "/", "name": "home"})
        for feature in features:
            if isinstance(feature, str):
                slug = feature.lower().replace(" ", "-")[:32]
                routes.append({"path": f"/{slug}", "name": slug.replace("-", "_")})
        # Common routes
        routes.extend([
            {"path": "/login", "name": "login"},
            {"path": "/register", "name": "register"},
            {"path": "/dashboard", "name": "dashboard"},
            {"path": "/settings", "name": "settings"},
        ])

    return routes


def _build_default_routes(state: PipelineState) -> dict[str, str]:
    """Build deterministic default route files from pipeline state."""
    idea_spec = state.get("idea_spec", {})
    title = str(idea_spec.get("title", "App"))
    framework = str(idea_spec.get("framework", "react_vite"))
    is_nextjs = "next" in framework.lower()

    routes = _extract_routes(state)
    files: dict[str, str] = {}

    if is_nextjs:
        # Next.js App Router layout
        files["app/layout.tsx"] = (
            "import type { Metadata } from 'next';\n"
            "import './globals.css';\n\n"
            f"export const metadata: Metadata = {{\n"
            f"  title: '{title}',\n"
            f"  description: '{title} — built with FORGE',\n"
            "}};\n\n"
            "interface RootLayoutProps {\n"
            "  children: React.ReactNode;\n"
            "}\n\n"
            "export default function RootLayout({ children }: RootLayoutProps) {\n"
            "  return (\n"
            "    <html lang=\"en\">\n"
            "      <body>{children}</body>\n"
            "    </html>\n"
            "  );\n"
            "}\n"
        )

        # Generate each route as a Next.js page
        for route in routes:
            path = route.get("path", "/")
            name = route.get("name", "page")
            component_name = "".join(
                w.capitalize() for w in name.replace("-", "_").split("_")
            ) + "Page"

            if path == "/":
                file_path = "app/page.tsx"
            else:
                segments = path.strip("/")
                file_path = f"app/{segments}/page.tsx"

            files[file_path] = (
                f"export default function {component_name}() {{\n"
                f"  return (\n"
                f"    <main>\n"
                f"      <h1>{name.replace('_', ' ').title()}</h1>\n"
                f"    </main>\n"
                f"  );\n"
                f"}}\n"
            )
    else:
        # React Router (Vite) setup
        files["src/App.tsx"] = (
            "import { BrowserRouter, Routes, Route } from 'react-router-dom';\n"
            "import Layout from './components/Layout';\n"
        )
        # Import statements for each route
        imports: list[str] = []
        route_elements: list[str] = []

        for route in routes:
            path = route.get("path", "/")
            name = route.get("name", "page")
            component_name = "".join(
                w.capitalize() for w in name.replace("-", "_").split("_")
            ) + "Page"
            page_path = name.replace("-", "_")

            imports.append(
                f"import {component_name} from './pages/{page_path}';"
            )
            route_elements.append(
                f'          <Route path="{path}" element={{<{component_name} />}} />'
            )

            # Create the page file
            files[f"src/pages/{page_path}.tsx"] = (
                f"export default function {component_name}() {{\n"
                f"  return (\n"
                f"    <main>\n"
                f"      <h1>{name.replace('_', ' ').title()}</h1>\n"
                f"    </main>\n"
                f"  );\n"
                f"}}\n"
            )

        files["src/App.tsx"] = (
            "import { BrowserRouter, Routes, Route } from 'react-router-dom';\n"
            "import Layout from './components/Layout';\n"
            + "\n".join(imports)
            + "\n\n"
            "export default function App() {\n"
            "  return (\n"
            "    <BrowserRouter>\n"
            "      <Layout>\n"
            "        <Routes>\n"
            + "\n".join(route_elements)
            + "\n"
            "        </Routes>\n"
            "      </Layout>\n"
            "    </BrowserRouter>\n"
            "  );\n"
            "}\n"
        )

        # Layout component
        files["src/components/Layout.tsx"] = (
            "interface LayoutProps {\n"
            "  children: React.ReactNode;\n"
            "}\n\n"
            "export default function Layout({ children }: LayoutProps) {\n"
            "  return (\n"
            "    <div className=\"min-h-screen\">\n"
            "      <header className=\"border-b p-4\">\n"
            f"        <h1 className=\"text-xl font-bold\">{title}</h1>\n"
            "      </header>\n"
            "      <main className=\"p-4\">{children}</main>\n"
            "    </div>\n"
            "  );\n"
            "}\n"
        )

    return files


async def run_router_agent(
    state: PipelineState,
    ai_router: AIRouter,
    context_window_manager: ContextWindowManager,
) -> dict[str, str]:
    """Generate all route/page skeleton files.

    Architecture rule #4: temperature=0, fixed seed.
    Architecture rule #6: route list injected from comprehensive_plan.

    Returns
    -------
    dict[str, str]
        Mapping of file_path → file_content.
    """
    start = time.monotonic()
    idea_spec = state.get("idea_spec", {})
    plan = state.get("comprehensive_plan", {})
    injected_schemas = state.get("injected_schemas", {})

    routes = _extract_routes(state)
    route_summary = "\n".join(
        f"  - {r.get('path', '/')} → {r.get('name', 'page')}"
        for r in routes
    )

    user_prompt = (
        f"Project: {idea_spec.get('title', 'Untitled')}\n"
        f"Framework: {idea_spec.get('framework', 'react_vite')}\n"
        f"\nRoutes to generate:\n{route_summary}\n"
        f"\nComprehensive Plan Summary:\n"
        f"{plan.get('executive_summary', 'No plan available')}\n"
    )

    try:
        files = await context_window_manager.generate(
            system_prompt=_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            agent_name=AGENT_NAME,
        )
        if files:
            elapsed = time.monotonic() - start
            logger.info(
                "router_agent.complete",
                elapsed_s=round(elapsed, 3),
                files=len(files),
            )
            return files
    except Exception as exc:
        logger.warning("router_agent.llm_fallback", error=str(exc))

    files = _build_default_routes(state)
    elapsed = time.monotonic() - start
    logger.info(
        "router_agent.complete_default",
        elapsed_s=round(elapsed, 3),
        files=len(files),
    )
    return files

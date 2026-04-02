"""
API Agent (Agent 5) — generates all API routes.

Layer 2 inject: full OpenAPI 3.1 spec.
Layer 5: API contract validator confirms output matches spec after generation.
Files: app/api/ or fastapi routes — every endpoint from the spec.
Gate G7 after.
"""

from __future__ import annotations

import json
import time
from typing import Any

import structlog

from app.agents.ai_router import AIRouter
from app.agents.build.context_window_manager import ContextWindowManager
from app.agents.state import PipelineState

logger = structlog.get_logger(__name__)

AGENT_NAME = "api"

_SYSTEM_PROMPT = """You are a senior backend engineer generating API route handlers.
Implement EXACTLY to the OpenAPI spec provided.

Return a JSON object where keys are file paths and values are file contents.
Requirements:
- Implement every endpoint from the OpenAPI spec
- TypeScript for Next.js API routes; Python for FastAPI
- Input validation with Zod (TS) or Pydantic (Python)
- Proper error handling with consistent error response format
- Authentication middleware where required
- Rate limiting annotations where specified"""


def _extract_endpoints(state: PipelineState) -> list[dict[str, Any]]:
    """Extract API endpoint definitions from injected schemas or plan."""
    injected = state.get("injected_schemas", {})
    endpoints: list[dict[str, Any]] = []

    openapi_raw = injected.get("openapi_spec", "")
    if openapi_raw:
        try:
            spec = json.loads(openapi_raw) if isinstance(openapi_raw, str) else openapi_raw
            paths = spec.get("paths", {})
            for path, methods in paths.items():
                if isinstance(methods, dict):
                    for method, details in methods.items():
                        if method.lower() in ("get", "post", "put", "patch", "delete"):
                            endpoints.append({
                                "path": path,
                                "method": method.upper(),
                                "summary": details.get("summary", ""),
                                "auth_required": "security" in details,
                            })
        except (json.JSONDecodeError, AttributeError):
            pass

    if not endpoints:
        endpoints = [
            {"path": "/api/health", "method": "GET", "summary": "Health check", "auth_required": False},
            {"path": "/api/auth/login", "method": "POST", "summary": "User login", "auth_required": False},
            {"path": "/api/auth/register", "method": "POST", "summary": "User registration", "auth_required": False},
            {"path": "/api/auth/me", "method": "GET", "summary": "Current user", "auth_required": True},
            {"path": "/api/users", "method": "GET", "summary": "List users", "auth_required": True},
            {"path": "/api/users/{id}", "method": "GET", "summary": "Get user", "auth_required": True},
        ]

    return endpoints


def _build_default_api(state: PipelineState) -> dict[str, str]:
    """Build deterministic default API route files."""
    idea = state.get("idea_spec", {})
    framework = str(idea.get("framework", "react_vite"))
    is_nextjs = "next" in framework.lower()
    endpoints = _extract_endpoints(state)
    files: dict[str, str] = {}

    if is_nextjs:
        # Next.js API routes
        for ep in endpoints:
            path = ep["path"].replace("/api/", "")
            method = ep["method"]
            summary = ep["summary"]
            segments = path.replace("{", "[").replace("}", "]")
            fp = f"app/api/{segments}/route.ts"

            handler = (
                f"import {{ NextRequest, NextResponse }} from 'next/server';\n\n"
                f"// {summary}\n"
                f"export async function {method}(request: NextRequest) {{\n"
                f"  try {{\n"
                f"    return NextResponse.json({{ message: '{summary}' }});\n"
                f"  }} catch (error: unknown) {{\n"
                f"    const message = error instanceof Error ? error.message : 'Internal error';\n"
                f"    return NextResponse.json({{ error: message }}, {{ status: 500 }});\n"
                f"  }}\n"
                f"}}\n"
            )
            files[fp] = handler
    else:
        # Express-style or lib/api module
        files["src/lib/api/client.ts"] = (
            "import axios from 'axios';\n\n"
            "const apiClient = axios.create({\n"
            "  baseURL: import.meta.env.VITE_API_URL ?? '/api',\n"
            "  headers: { 'Content-Type': 'application/json' },\n"
            "  timeout: 10000,\n"
            "});\n\n"
            "apiClient.interceptors.request.use((config) => {\n"
            "  const token = localStorage.getItem('auth_token');\n"
            "  if (token && config.headers) {\n"
            "    config.headers.Authorization = `Bearer ${token}`;\n"
            "  }\n"
            "  return config;\n"
            "});\n\n"
            "apiClient.interceptors.response.use(\n"
            "  (response) => response,\n"
            "  (error) => {\n"
            "    if (error.response?.status === 401) {\n"
            "      localStorage.removeItem('auth_token');\n"
            "      window.location.href = '/login';\n"
            "    }\n"
            "    return Promise.reject(error);\n"
            "  }\n"
            ");\n\n"
            "export default apiClient;\n"
        )

        # Generate typed API functions
        api_funcs: list[str] = [
            "import apiClient from './client';\n",
            "// Auto-generated API functions\n",
        ]
        for ep in endpoints:
            path = ep["path"]
            method = ep["method"].lower()
            name_parts = path.replace("/api/", "").replace("{", "").replace("}", "").split("/")
            fn_name = method + "".join(w.capitalize() for w in name_parts if w)

            ts_path = path.replace("{", "${")
            if method == "get":
                api_funcs.append(
                    f"export async function {fn_name}() {{\n"
                    f"  const {{ data }} = await apiClient.get('{ts_path}');\n"
                    f"  return data;\n"
                    f"}}\n"
                )
            elif method in ("post", "put", "patch"):
                api_funcs.append(
                    f"export async function {fn_name}(body: Record<string, unknown>) {{\n"
                    f"  const {{ data }} = await apiClient.{method}('{ts_path}', body);\n"
                    f"  return data;\n"
                    f"}}\n"
                )
            else:
                api_funcs.append(
                    f"export async function {fn_name}() {{\n"
                    f"  const {{ data }} = await apiClient.{method}('{ts_path}');\n"
                    f"  return data;\n"
                    f"}}\n"
                )

        files["src/lib/api/endpoints.ts"] = "\n".join(api_funcs)

        # Index barrel
        files["src/lib/api/index.ts"] = (
            "export { default as apiClient } from './client';\n"
            "export * from './endpoints';\n"
        )

    return files


async def run_api_agent(
    state: PipelineState,
    ai_router: AIRouter,
    context_window_manager: ContextWindowManager,
) -> dict[str, str]:
    """Generate API route files. temp=0, OpenAPI spec injection."""
    start = time.monotonic()
    idea = state.get("idea_spec", {})
    injected = state.get("injected_schemas", {})

    openapi_ctx = ""
    if "openapi_spec" in injected:
        openapi_ctx = f"\nOpenAPI Spec:\n{str(injected['openapi_spec'])[:4000]}\n"

    user_prompt = (
        f"Project: {idea.get('title', 'Untitled')}\n"
        f"Framework: {idea.get('framework', 'react_vite')}\n"
        f"{openapi_ctx}"
    )

    try:
        files = await context_window_manager.generate(
            system_prompt=_SYSTEM_PROMPT, user_prompt=user_prompt, agent_name=AGENT_NAME,
        )
        if files:
            logger.info("api_agent.complete", elapsed_s=round(time.monotonic() - start, 3), files=len(files))
            return files
    except Exception as exc:
        logger.warning("api_agent.llm_fallback", error=str(exc))

    files = _build_default_api(state)
    logger.info("api_agent.complete_default", elapsed_s=round(time.monotonic() - start, 3), files=len(files))
    return files

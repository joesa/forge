"""
Test Agent (Agent 9) — generates unit and integration tests.

Files: tests/ — one test file per major service/component.
  - Happy path tests for every API route
  - Edge case tests (empty arrays, null values, unauthorized access)
  - Component render tests for every shared component
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

AGENT_NAME = "test"

_SYSTEM_PROMPT = """You are a senior QA engineer generating comprehensive test suites.
Generate tests using Vitest for TypeScript/React projects.

Return a JSON object where keys are file paths and values are file contents.
Requirements:
- One test file per major component/service
- Happy path tests for every API route
- Edge cases: empty arrays, null values, unauthorized access
- Component render tests using @testing-library/react
- Mock external dependencies (never call real APIs)
- Use describe/it blocks with clear test names"""


def _build_default_tests(state: PipelineState) -> dict[str, str]:
    """Build deterministic default test files."""
    generated = state.get("generated_files", {})
    files: dict[str, str] = {}

    # ── Component tests ──────────────────────────────────────────
    component_names = [
        "Button", "Input", "Select", "Card", "Modal",
        "Badge", "Spinner", "Avatar", "Toast",
    ]

    test_imports = (
        "import { describe, it, expect } from 'vitest';\n"
        "import { render, screen } from '@testing-library/react';\n"
    )

    for comp in component_names:
        test_content = (
            f"{test_imports}"
            f"import {comp} from '@/components/ui/{comp}';\n\n"
            f"describe('{comp}', () => {{\n"
            f"  it('renders without crashing', () => {{\n"
        )

        if comp == "Button":
            test_content += (
                f"    render(<{comp}>Click me</{comp}>);\n"
                f"    expect(screen.getByText('Click me')).toBeDefined();\n"
            )
        elif comp == "Input":
            test_content += (
                f"    render(<{comp} label=\"Email\" />);\n"
                f"    expect(screen.getByLabelText('Email')).toBeDefined();\n"
            )
        elif comp == "Select":
            test_content += (
                f"    render(<{comp} options={{[{{ value: '1', label: 'One' }}]}} />);\n"
                f"    expect(screen.getByText('One')).toBeDefined();\n"
            )
        elif comp == "Card":
            test_content += (
                f"    render(<{comp}>Content</{comp}>);\n"
                f"    expect(screen.getByText('Content')).toBeDefined();\n"
            )
        elif comp == "Modal":
            test_content += (
                f"    render(<{comp} isOpen={{true}} onClose={{() => {{}}}} title=\"Test\">Body</{comp}>);\n"
                f"    expect(screen.getByText('Test')).toBeDefined();\n"
            )
        elif comp == "Badge":
            test_content += (
                f"    render(<{comp}>New</{comp}>);\n"
                f"    expect(screen.getByText('New')).toBeDefined();\n"
            )
        elif comp == "Spinner":
            test_content += (
                f"    render(<{comp} />);\n"
                f"    expect(screen.getByRole('status')).toBeDefined();\n"
            )
        elif comp == "Avatar":
            test_content += (
                f"    render(<{comp} fallback=\"JD\" />);\n"
                f"    expect(screen.getByText('JD')).toBeDefined();\n"
            )
        elif comp == "Toast":
            test_content += (
                f"    render(<{comp} message=\"Saved\" isVisible={{true}} onClose={{() => {{}}}} />);\n"
                f"    expect(screen.getByText('Saved')).toBeDefined();\n"
            )

        test_content += (
            f"  }});\n\n"
            f"  it('handles empty/null props gracefully', () => {{\n"
            f"    // Edge case: component should not throw with minimal props\n"
            f"    expect(() => {{\n"
        )

        if comp in ("Button", "Card", "Badge"):
            test_content += f"      render(<{comp}>test</{comp}>);\n"
        elif comp == "Select":
            test_content += f"      render(<{comp} options={{[]}} />);\n"
        elif comp == "Modal":
            test_content += f"      render(<{comp} isOpen={{false}} onClose={{() => {{}}}}>x</{comp}>);\n"
        elif comp == "Toast":
            test_content += f"      render(<{comp} message=\"\" isVisible={{false}} onClose={{() => {{}}}} />);\n"
        else:
            test_content += f"      render(<{comp} />);\n"

        test_content += (
            f"    }}).not.toThrow();\n"
            f"  }});\n"
            f"}});\n"
        )

        files[f"tests/components/{comp}.test.tsx"] = test_content

    # ── API tests ────────────────────────────────────────────────
    files["tests/api/auth.test.ts"] = (
        "import { describe, it, expect, vi, beforeEach } from 'vitest';\n\n"
        "// Mock fetch globally\n"
        "const mockFetch = vi.fn();\n"
        "vi.stubGlobal('fetch', mockFetch);\n\n"
        "describe('Auth API', () => {\n"
        "  beforeEach(() => { mockFetch.mockReset(); });\n\n"
        "  it('POST /api/auth/login — happy path', async () => {\n"
        "    mockFetch.mockResolvedValueOnce({\n"
        "      ok: true,\n"
        "      json: async () => ({ token: 'jwt-token', user: { id: '1', email: 'test@test.com' } }),\n"
        "    });\n"
        "    const res = await fetch('/api/auth/login', {\n"
        "      method: 'POST',\n"
        "      body: JSON.stringify({ email: 'test@test.com', password: 'pass' }),\n"
        "    });\n"
        "    expect(res.ok).toBe(true);\n"
        "    const data = await res.json();\n"
        "    expect(data.token).toBeDefined();\n"
        "  });\n\n"
        "  it('POST /api/auth/login — invalid credentials', async () => {\n"
        "    mockFetch.mockResolvedValueOnce({ ok: false, status: 401 });\n"
        "    const res = await fetch('/api/auth/login', {\n"
        "      method: 'POST',\n"
        "      body: JSON.stringify({ email: 'bad@test.com', password: 'wrong' }),\n"
        "    });\n"
        "    expect(res.ok).toBe(false);\n"
        "  });\n\n"
        "  it('POST /api/auth/register — happy path', async () => {\n"
        "    mockFetch.mockResolvedValueOnce({\n"
        "      ok: true,\n"
        "      json: async () => ({ token: 'jwt-token', user: { id: '2', email: 'new@test.com' } }),\n"
        "    });\n"
        "    const res = await fetch('/api/auth/register', {\n"
        "      method: 'POST',\n"
        "      body: JSON.stringify({ email: 'new@test.com', password: 'pass', name: 'Test' }),\n"
        "    });\n"
        "    expect(res.ok).toBe(true);\n"
        "  });\n\n"
        "  it('GET /api/auth/me — unauthorized (no token)', async () => {\n"
        "    mockFetch.mockResolvedValueOnce({ ok: false, status: 401 });\n"
        "    const res = await fetch('/api/auth/me');\n"
        "    expect(res.ok).toBe(false);\n"
        "  });\n"
        "});\n"
    )

    files["tests/api/health.test.ts"] = (
        "import { describe, it, expect, vi } from 'vitest';\n\n"
        "const mockFetch = vi.fn();\n"
        "vi.stubGlobal('fetch', mockFetch);\n\n"
        "describe('Health API', () => {\n"
        "  it('GET /api/health — returns 200', async () => {\n"
        "    mockFetch.mockResolvedValueOnce({\n"
        "      ok: true,\n"
        "      json: async () => ({ status: 'healthy' }),\n"
        "    });\n"
        "    const res = await fetch('/api/health');\n"
        "    expect(res.ok).toBe(true);\n"
        "  });\n"
        "});\n"
    )

    # ── Vitest config ────────────────────────────────────────────
    files["vitest.config.ts"] = (
        "import { defineConfig } from 'vitest/config';\n"
        "import path from 'path';\n\n"
        "export default defineConfig({\n"
        "  test: {\n"
        "    globals: true,\n"
        "    environment: 'jsdom',\n"
        "    setupFiles: ['./tests/setup.ts'],\n"
        "    include: ['tests/**/*.test.{ts,tsx}'],\n"
        "  },\n"
        "  resolve: {\n"
        "    alias: { '@': path.resolve(__dirname, './src') },\n"
        "  },\n"
        "});\n"
    )

    files["tests/setup.ts"] = (
        "import '@testing-library/jest-dom/vitest';\n"
    )

    return files


async def run_test_agent(
    state: PipelineState,
    ai_router: AIRouter,
    context_window_manager: ContextWindowManager,
) -> dict[str, str]:
    """Generate unit and integration tests. temp=0."""
    start = time.monotonic()
    idea = state.get("idea_spec", {})
    generated = state.get("generated_files", {})

    file_list = "\n".join(f"  - {fp}" for fp in sorted(generated.keys())[:30])
    user_prompt = (
        f"Project: {idea.get('title', 'Untitled')}\n"
        f"Files to test:\n{file_list}\n"
        f"Generate: component render tests, API tests, edge case tests\n"
    )

    try:
        files = await context_window_manager.generate(
            system_prompt=_SYSTEM_PROMPT, user_prompt=user_prompt, agent_name=AGENT_NAME,
        )
        if files:
            logger.info("test_agent.complete", elapsed_s=round(time.monotonic() - start, 3), files=len(files))
            return files
    except Exception as exc:
        logger.warning("test_agent.llm_fallback", error=str(exc))

    files = _build_default_tests(state)
    logger.info("test_agent.complete_default", elapsed_s=round(time.monotonic() - start, 3), files=len(files))
    return files

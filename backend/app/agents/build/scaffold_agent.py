"""
Scaffold Agent (Agent 1) — generates project scaffold files.

Layer 1 runs BEFORE this agent:
  - dependency_resolver resolves all deps
  - env_contract_validator confirms required env vars exist
  - lockfile_generator creates package-lock.json

Files generated:
  - package.json (pinned versions from resolved_dependencies)
  - tsconfig.json
  - vite.config.ts or next.config.ts (based on framework)
  - tailwind.config.ts
  - .env.example (from env_contract)
  - .gitignore
  - .eslintrc.json
  - .prettierrc
  - .github/workflows/ci.yml

Gate G7 after: TypeScript compilation check on tsconfig.json.
"""

from __future__ import annotations

import json
import time
from typing import Any

import structlog

from app.agents.ai_router import AIRouter
from app.agents.build.context_window_manager import ContextWindowManager
from app.agents.state import PipelineState
from app.reliability.layer1_pregeneration import (
    generate_lockfile,
)

logger = structlog.get_logger(__name__)

AGENT_NAME = "scaffold"

_SYSTEM_PROMPT = """You are a senior full-stack engineer generating a project scaffold.
Generate all configuration files for the project based on the resolved dependencies
and environment contract. Every dependency version must be pinned (no ^ or ~).

Return a JSON object where keys are file paths and values are file contents.
Example: {"package.json": "...", "tsconfig.json": "...", ...}

Requirements:
- package.json: use exact pinned versions from the resolved dependencies
- tsconfig.json: strict mode, path aliases
- vite.config.ts or next.config.ts: based on framework
- tailwind.config.ts: with content paths configured
- .env.example: list all required/optional vars with comments
- .gitignore: comprehensive for Node.js/TypeScript projects
- .eslintrc.json: TypeScript-aware rules
- .prettierrc: consistent formatting
- .github/workflows/ci.yml: lint, typecheck, test, build"""


def _build_default_scaffold(
    state: PipelineState,
) -> dict[str, str]:
    """Build a deterministic default scaffold from pipeline state.

    Uses resolved_dependencies and env_contract from Stage 1.
    """
    idea_spec = state.get("idea_spec", {})
    resolved_deps = state.get("resolved_dependencies", {})
    env_contract = state.get("env_contract", {})

    title = str(idea_spec.get("title", "forge-app"))
    # Sanitize title for package name
    pkg_name = title.lower().replace(" ", "-").replace("_", "-")[:64]

    # Get packages from resolved dependencies
    packages: dict[str, str] = {}
    if isinstance(resolved_deps, dict):
        packages = resolved_deps.get("packages", {})

    # Determine framework
    framework = str(idea_spec.get("framework", "react_vite"))
    is_nextjs = "next" in framework.lower()

    # ── package.json ─────────────────────────────────────────────
    deps: dict[str, str] = {}
    dev_deps: dict[str, str] = {}

    for pkg, version in sorted(packages.items()):
        if pkg in ("typescript", "tailwindcss", "postcss", "autoprefixer",
                    "@vitejs/plugin-react", "vite"):
            dev_deps[pkg] = version
        else:
            deps[pkg] = version

    # Ensure core deps exist
    if "react" not in deps:
        deps["react"] = "18.3.1"
    if "react-dom" not in deps:
        deps["react-dom"] = "18.3.1"
    if "typescript" not in dev_deps:
        dev_deps["typescript"] = "5.4.5"

    package_json = {
        "name": pkg_name,
        "private": True,
        "version": "1.0.0",
        "type": "module",
        "scripts": {
            "dev": "next dev" if is_nextjs else "vite",
            "build": "next build" if is_nextjs else "tsc && vite build",
            "preview": "vite preview" if not is_nextjs else "next start",
            "lint": "eslint . --ext .ts,.tsx --report-unused-disable-directives --max-warnings 0",
            "typecheck": "tsc --noEmit",
            "test": "vitest run",
        },
        "dependencies": dict(sorted(deps.items())),
        "devDependencies": dict(sorted(dev_deps.items())),
    }

    # ── tsconfig.json ────────────────────────────────────────────
    tsconfig = {
        "compilerOptions": {
            "target": "ES2022",
            "lib": ["ES2022", "DOM", "DOM.Iterable"],
            "module": "ESNext",
            "skipLibCheck": True,
            "moduleResolution": "bundler",
            "allowImportingTsExtensions": True,
            "resolveJsonModule": True,
            "isolatedModules": True,
            "noEmit": True,
            "jsx": "react-jsx",
            "strict": True,
            "noUnusedLocals": True,
            "noUnusedParameters": True,
            "noFallthroughCasesInSwitch": True,
            "noUncheckedIndexedAccess": True,
            "baseUrl": ".",
            "paths": {
                "@/*": ["./src/*"],
                "@/components/*": ["./src/components/*"],
                "@/lib/*": ["./src/lib/*"],
                "@/hooks/*": ["./src/hooks/*"],
                "@/types/*": ["./src/types/*"],
            },
        },
        "include": ["src"],
        "references": [{"path": "./tsconfig.node.json"}],
    }

    # ── vite.config.ts or next.config.ts ─────────────────────────
    if is_nextjs:
        bundler_config_path = "next.config.ts"
        bundler_config = (
            "import type { NextConfig } from 'next';\n\n"
            "const nextConfig: NextConfig = {\n"
            "  reactStrictMode: true,\n"
            "  typescript: { ignoreBuildErrors: false },\n"
            "  eslint: { ignoreDuringBuilds: false },\n"
            "};\n\n"
            "export default nextConfig;\n"
        )
    else:
        bundler_config_path = "vite.config.ts"
        bundler_config = (
            "import { defineConfig } from 'vite';\n"
            "import react from '@vitejs/plugin-react';\n"
            "import path from 'path';\n\n"
            "export default defineConfig({\n"
            "  plugins: [react()],\n"
            "  resolve: {\n"
            "    alias: {\n"
            "      '@': path.resolve(__dirname, './src'),\n"
            "    },\n"
            "  },\n"
            "  server: {\n"
            "    port: 5173,\n"
            "    strictPort: true,\n"
            "  },\n"
            "  build: {\n"
            "    sourcemap: true,\n"
            "    target: 'es2022',\n"
            "  },\n"
            "});\n"
        )

    # ── tailwind.config.ts ───────────────────────────────────────
    tailwind_config = (
        "import type { Config } from 'tailwindcss';\n\n"
        "const config: Config = {\n"
        "  content: [\n"
        "    './index.html',\n"
        "    './src/**/*.{js,ts,jsx,tsx}',\n"
        "  ],\n"
        "  theme: {\n"
        "    extend: {},\n"
        "  },\n"
        "  plugins: [],\n"
        "};\n\n"
        "export default config;\n"
    )

    # ── .env.example ─────────────────────────────────────────────
    env_lines: list[str] = ["# Environment Variables", "# Auto-generated by FORGE scaffold agent", ""]
    required_vars: list[dict[str, Any]] = []
    optional_vars: list[dict[str, Any]] = []
    if isinstance(env_contract, dict):
        required_vars = env_contract.get("required", [])
        optional_vars = env_contract.get("optional", [])

    if required_vars:
        env_lines.append("# ── Required ─────────────────────────")
        for var in required_vars:
            if isinstance(var, dict):
                name = var.get("name", "")
                desc = var.get("description", "")
                example = var.get("example", "")
                env_lines.append(f"# {desc}")
                env_lines.append(f"{name}={example}")
                env_lines.append("")

    if optional_vars:
        env_lines.append("# ── Optional ─────────────────────────")
        for var in optional_vars:
            if isinstance(var, dict):
                name = var.get("name", "")
                desc = var.get("description", "")
                example = var.get("example", "")
                env_lines.append(f"# {desc}")
                env_lines.append(f"# {name}={example}")
                env_lines.append("")

    env_example = "\n".join(env_lines) + "\n"

    # ── .gitignore ───────────────────────────────────────────────
    gitignore = (
        "# Dependencies\nnode_modules/\n\n"
        "# Build output\ndist/\n.next/\nout/\nbuild/\n\n"
        "# Environment\n.env\n.env.local\n.env.*.local\n\n"
        "# IDE\n.vscode/\n.idea/\n*.swp\n*.swo\n\n"
        "# OS\n.DS_Store\nThumbs.db\n\n"
        "# Test coverage\ncoverage/\n\n"
        "# TypeScript cache\n*.tsbuildinfo\n\n"
        "# Debug logs\nnpm-debug.log*\nyarn-debug.log*\nyarn-error.log*\n"
    )

    # ── .eslintrc.json ───────────────────────────────────────────
    eslintrc = {
        "root": True,
        "env": {"browser": True, "es2022": True},
        "extends": [
            "eslint:recommended",
            "plugin:@typescript-eslint/recommended",
            "plugin:react-hooks/recommended",
        ],
        "ignorePatterns": ["dist", ".eslintrc.json"],
        "parser": "@typescript-eslint/parser",
        "parserOptions": {
            "ecmaVersion": "latest",
            "sourceType": "module",
        },
        "plugins": ["react-refresh"],
        "rules": {
            "react-refresh/only-export-components": [
                "warn",
                {"allowConstantExport": True},
            ],
            "@typescript-eslint/no-explicit-any": "error",
            "@typescript-eslint/no-unused-vars": [
                "error",
                {"argsIgnorePattern": "^_"},
            ],
        },
    }

    # ── .prettierrc ──────────────────────────────────────────────
    prettierrc = {
        "semi": True,
        "trailingComma": "all",
        "singleQuote": True,
        "printWidth": 100,
        "tabWidth": 2,
        "useTabs": False,
    }

    # ── CI workflow ──────────────────────────────────────────────
    ci_workflow = (
        "name: CI\n\n"
        "on:\n"
        "  push:\n"
        "    branches: [main]\n"
        "  pull_request:\n"
        "    branches: [main]\n\n"
        "jobs:\n"
        "  build:\n"
        "    runs-on: ubuntu-latest\n"
        "    steps:\n"
        "      - uses: actions/checkout@v4\n"
        "      - uses: actions/setup-node@v4\n"
        "        with:\n"
        "          node-version: '20'\n"
        "          cache: 'npm'\n"
        "      - run: npm ci\n"
        "      - run: npm run lint\n"
        "      - run: npm run typecheck\n"
        "      - run: npm run test\n"
        "      - run: npm run build\n"
    )

    # ── package-lock.json (from lockfile generator) ──────────────
    lockfile_content = generate_lockfile(packages) if packages else ""

    # ── Assemble output ──────────────────────────────────────────
    files: dict[str, str] = {
        "package.json": json.dumps(package_json, indent=2) + "\n",
        "tsconfig.json": json.dumps(tsconfig, indent=2) + "\n",
        bundler_config_path: bundler_config,
        "tailwind.config.ts": tailwind_config,
        ".env.example": env_example,
        ".gitignore": gitignore,
        ".eslintrc.json": json.dumps(eslintrc, indent=2) + "\n",
        ".prettierrc": json.dumps(prettierrc, indent=2) + "\n",
        ".github/workflows/ci.yml": ci_workflow,
    }
    if lockfile_content:
        files["package-lock.json"] = lockfile_content

    return files


async def run_scaffold_agent(
    state: PipelineState,
    ai_router: AIRouter,
    context_window_manager: ContextWindowManager,
) -> dict[str, str]:
    """Generate the project scaffold.

    Architecture rule #4: temperature=0, fixed seed (deterministic).
    Architecture rule #6: Layer 1 contracts already ran in Stage 1.

    Parameters
    ----------
    state : PipelineState
        Current pipeline state (includes resolved_dependencies, env_contract).
    ai_router : AIRouter
        LLM router for code generation.
    context_window_manager : ContextWindowManager
        Handles context window splitting.

    Returns
    -------
    dict[str, str]
        Mapping of file_path → file_content.
    """
    start = time.monotonic()
    idea_spec = state.get("idea_spec", {})

    # Build the prompt with all available context
    user_prompt = (
        f"Project: {idea_spec.get('title', 'Untitled')}\n"
        f"Description: {idea_spec.get('description', 'No description')}\n"
        f"Framework: {idea_spec.get('framework', 'react_vite')}\n"
        f"Features: {', '.join(str(f) for f in idea_spec.get('features', []))}\n"
        f"\nResolved Dependencies:\n"
        f"{json.dumps(state.get('resolved_dependencies', {}), indent=2)}\n"
        f"\nEnvironment Contract:\n"
        f"{json.dumps(state.get('env_contract', {}), indent=2)}"
    )

    try:
        files = await context_window_manager.generate(
            system_prompt=_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            agent_name=AGENT_NAME,
        )
        # If LLM returns files, use them
        if files:
            elapsed = time.monotonic() - start
            logger.info(
                "scaffold_agent.complete",
                elapsed_s=round(elapsed, 3),
                files=len(files),
            )
            return files
    except Exception as exc:
        logger.warning("scaffold_agent.llm_fallback", error=str(exc))

    # Fallback: use deterministic defaults
    files = _build_default_scaffold(state)
    elapsed = time.monotonic() - start
    logger.info(
        "scaffold_agent.complete_default",
        elapsed_s=round(elapsed, 3),
        files=len(files),
    )
    return files

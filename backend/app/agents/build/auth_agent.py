"""
Auth Agent (Agent 7) — generates authentication system.

Layer 5: uses auth_jwt or oauth_pkce pattern from pattern_library.
Files: auth middleware, login/register pages, session helpers, protected routes.
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

AGENT_NAME = "auth"

_SYSTEM_PROMPT = """You are a senior security engineer generating an authentication system.
Generate authentication files with JWT-based auth, session management, and protected routes.

Return a JSON object where keys are file paths and values are file contents.
Requirements:
- JWT token handling (access + refresh tokens)
- Login and register API integration
- Session persistence (localStorage/cookies)
- Auth context provider for React
- Protected route wrapper component
- Middleware for authenticated API calls"""


def _build_default_auth(state: PipelineState) -> dict[str, str]:
    """Build deterministic default authentication files."""
    files: dict[str, str] = {}

    # Auth context/provider
    files["src/lib/auth/AuthContext.tsx"] = (
        "import React, { createContext, useContext, useEffect, useState } from 'react';\n\n"
        "interface User {\n  id: string;\n  email: string;\n  name: string;\n}\n\n"
        "interface AuthContextType {\n  user: User | null;\n  isLoading: boolean;\n"
        "  login: (email: string, password: string) => Promise<void>;\n"
        "  register: (email: string, password: string, name: string) => Promise<void>;\n"
        "  logout: () => void;\n  isAuthenticated: boolean;\n}\n\n"
        "const AuthContext = createContext<AuthContextType | undefined>(undefined);\n\n"
        "export function AuthProvider({ children }: { children: React.ReactNode }) {\n"
        "  const [user, setUser] = useState<User | null>(null);\n"
        "  const [isLoading, setIsLoading] = useState(true);\n\n"
        "  useEffect(() => {\n"
        "    const token = localStorage.getItem('auth_token');\n"
        "    if (token) {\n"
        "      fetchCurrentUser(token).then(setUser).catch(() => localStorage.removeItem('auth_token')).finally(() => setIsLoading(false));\n"
        "    } else { setIsLoading(false); }\n"
        "  }, []);\n\n"
        "  const login = async (email: string, password: string) => {\n"
        "    const res = await fetch('/api/auth/login', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ email, password }) });\n"
        "    if (!res.ok) throw new Error('Login failed');\n"
        "    const data = await res.json();\n"
        "    localStorage.setItem('auth_token', data.token);\n"
        "    setUser(data.user);\n"
        "  };\n\n"
        "  const register = async (email: string, password: string, name: string) => {\n"
        "    const res = await fetch('/api/auth/register', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ email, password, name }) });\n"
        "    if (!res.ok) throw new Error('Registration failed');\n"
        "    const data = await res.json();\n"
        "    localStorage.setItem('auth_token', data.token);\n"
        "    setUser(data.user);\n"
        "  };\n\n"
        "  const logout = () => { localStorage.removeItem('auth_token'); setUser(null); };\n\n"
        "  return <AuthContext.Provider value={{ user, isLoading, login, register, logout, isAuthenticated: !!user }}>{children}</AuthContext.Provider>;\n"
        "}\n\n"
        "async function fetchCurrentUser(token: string): Promise<User> {\n"
        "  const res = await fetch('/api/auth/me', { headers: { Authorization: `Bearer ${token}` } });\n"
        "  if (!res.ok) throw new Error('Invalid token');\n"
        "  return res.json();\n"
        "}\n\n"
        "export function useAuth(): AuthContextType {\n"
        "  const ctx = useContext(AuthContext);\n"
        "  if (!ctx) throw new Error('useAuth must be used within AuthProvider');\n"
        "  return ctx;\n"
        "}\n\n"
        "export default AuthContext;\n"
    )

    # Protected route component
    files["src/lib/auth/ProtectedRoute.tsx"] = (
        "import React from 'react';\nimport { Navigate } from 'react-router-dom';\n"
        "import { useAuth } from './AuthContext';\nimport { Spinner } from '@/components/ui';\n\n"
        "interface ProtectedRouteProps { children: React.ReactNode; }\n\n"
        "export default function ProtectedRoute({ children }: ProtectedRouteProps) {\n"
        "  const { isAuthenticated, isLoading } = useAuth();\n"
        "  if (isLoading) return <div className=\"flex h-screen items-center justify-center\"><Spinner size=\"lg\" /></div>;\n"
        "  if (!isAuthenticated) return <Navigate to=\"/login\" replace />;\n"
        "  return <>{children}</>;\n"
        "}\n"
    )

    # Auth middleware for API calls
    files["src/lib/auth/middleware.ts"] = (
        "// Auth middleware — attaches JWT to outgoing requests\n\n"
        "export function getAuthHeaders(): Record<string, string> {\n"
        "  const token = localStorage.getItem('auth_token');\n"
        "  return token ? { Authorization: `Bearer ${token}` } : {};\n"
        "}\n\n"
        "export function isTokenExpired(token: string): boolean {\n"
        "  try {\n"
        "    const payload = JSON.parse(atob(token.split('.')[1]));\n"
        "    return payload.exp * 1000 < Date.now();\n"
        "  } catch { return true; }\n"
        "}\n\n"
        "export function clearAuth(): void {\n"
        "  localStorage.removeItem('auth_token');\n"
        "  localStorage.removeItem('refresh_token');\n"
        "}\n"
    )

    # Session helpers
    files["src/lib/auth/session.ts"] = (
        "// Session management helpers\n\n"
        "const TOKEN_KEY = 'auth_token';\nconst REFRESH_KEY = 'refresh_token';\n\n"
        "export function setTokens(access: string, refresh?: string): void {\n"
        "  localStorage.setItem(TOKEN_KEY, access);\n"
        "  if (refresh) localStorage.setItem(REFRESH_KEY, refresh);\n"
        "}\n\n"
        "export function getAccessToken(): string | null { return localStorage.getItem(TOKEN_KEY); }\n"
        "export function getRefreshToken(): string | null { return localStorage.getItem(REFRESH_KEY); }\n"
        "export function clearTokens(): void { localStorage.removeItem(TOKEN_KEY); localStorage.removeItem(REFRESH_KEY); }\n"
    )

    # Barrel
    files["src/lib/auth/index.ts"] = (
        "export { AuthProvider, useAuth } from './AuthContext';\n"
        "export { default as ProtectedRoute } from './ProtectedRoute';\n"
        "export { getAuthHeaders, isTokenExpired, clearAuth } from './middleware';\n"
        "export { setTokens, getAccessToken, getRefreshToken, clearTokens } from './session';\n"
    )

    return files


async def run_auth_agent(
    state: PipelineState,
    ai_router: AIRouter,
    context_window_manager: ContextWindowManager,
) -> dict[str, str]:
    """Generate authentication system. temp=0."""
    start = time.monotonic()
    idea = state.get("idea_spec", {})

    user_prompt = (
        f"Project: {idea.get('title', 'Untitled')}\n"
        f"Framework: {idea.get('framework', 'react_vite')}\n"
        f"Generate: JWT auth context, protected route, middleware, session helpers\n"
    )

    try:
        files = await context_window_manager.generate(
            system_prompt=_SYSTEM_PROMPT, user_prompt=user_prompt, agent_name=AGENT_NAME,
        )
        if files:
            logger.info("auth_agent.complete", elapsed_s=round(time.monotonic() - start, 3), files=len(files))
            return files
    except Exception as exc:
        logger.warning("auth_agent.llm_fallback", error=str(exc))

    files = _build_default_auth(state)
    logger.info("auth_agent.complete_default", elapsed_s=round(time.monotonic() - start, 3), files=len(files))
    return files

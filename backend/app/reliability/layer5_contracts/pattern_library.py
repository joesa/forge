"""
Layer 5 — Pattern library.

30+ proven implementation patterns for common full-stack features.
Each pattern includes: name, description, category, implementation template,
test template, and anti-patterns to avoid.

Used by build agents to inject battle-tested code patterns into generated apps.
"""

from __future__ import annotations

import re

from pydantic import BaseModel, Field

import structlog

logger = structlog.get_logger(__name__)


class Pattern(BaseModel):
    """A proven implementation pattern."""

    name: str
    description: str
    category: str = Field(
        description="auth | api | data | state | ui | form | infra | realtime"
    )
    tags: list[str] = Field(default_factory=list)
    implementation_template: str = ""
    test_template: str = ""
    anti_patterns: list[str] = Field(default_factory=list)


# ── Pattern registry ─────────────────────────────────────────────────

_PATTERN_REGISTRY: dict[str, Pattern] = {
    "auth_jwt": Pattern(
        name="auth_jwt",
        description="JWT validation middleware with JWKS verification",
        category="auth",
        tags=["authentication", "jwt", "middleware", "token", "login", "auth"],
        implementation_template=(
            "// JWT Auth Middleware\n"
            "import { NextRequest, NextResponse } from 'next/server';\n"
            "import jwt from 'jsonwebtoken';\n"
            "import jwksClient from 'jwks-rsa';\n\n"
            "const client = jwksClient({ jwksUri: process.env.JWKS_URI! });\n\n"
            "function getKey(header: jwt.JwtHeader, callback: jwt.SigningKeyCallback) {\n"
            "  client.getSigningKey(header.kid, (err, key) => {\n"
            "    callback(err, key?.getPublicKey());\n"
            "  });\n"
            "}\n\n"
            "export async function verifyToken(token: string): Promise<jwt.JwtPayload> {\n"
            "  return new Promise((resolve, reject) => {\n"
            "    jwt.verify(token, getKey, { algorithms: ['RS256'] }, (err, decoded) => {\n"
            "      if (err) reject(err);\n"
            "      else resolve(decoded as jwt.JwtPayload);\n"
            "    });\n"
            "  });\n"
            "}\n"
        ),
        test_template=(
            "describe('JWT Auth', () => {\n"
            "  it('rejects expired tokens', async () => {\n"
            "    await expect(verifyToken('expired.token')).rejects.toThrow();\n"
            "  });\n"
            "});\n"
        ),
        anti_patterns=[
            "Storing JWT in localStorage (use httpOnly cookies)",
            "Not validating token expiration",
            "Hardcoding JWKS URI instead of using environment variable",
        ],
    ),
    "oauth_pkce": Pattern(
        name="oauth_pkce",
        description="OAuth 2.0 PKCE flow for SPAs",
        category="auth",
        tags=["oauth", "pkce", "authentication", "social login", "sso"],
        implementation_template=(
            "// OAuth PKCE Flow\n"
            "function generateCodeVerifier(): string {\n"
            "  const array = new Uint8Array(32);\n"
            "  crypto.getRandomValues(array);\n"
            "  return btoa(String.fromCharCode(...array))\n"
            "    .replace(/\\+/g, '-').replace(/\\//g, '_').replace(/=+$/, '');\n"
            "}\n\n"
            "async function generateCodeChallenge(verifier: string): Promise<string> {\n"
            "  const encoder = new TextEncoder();\n"
            "  const data = encoder.encode(verifier);\n"
            "  const digest = await crypto.subtle.digest('SHA-256', data);\n"
            "  return btoa(String.fromCharCode(...new Uint8Array(digest)))\n"
            "    .replace(/\\+/g, '-').replace(/\\//g, '_').replace(/=+$/, '');\n"
            "}\n"
        ),
        test_template=(
            "describe('OAuth PKCE', () => {\n"
            "  it('generates valid code verifier', () => {\n"
            "    const verifier = generateCodeVerifier();\n"
            "    expect(verifier.length).toBeGreaterThan(42);\n"
            "  });\n"
            "});\n"
        ),
        anti_patterns=[
            "Using implicit grant flow instead of PKCE",
            "Storing code verifier in localStorage",
            "Not using S256 challenge method",
        ],
    ),
    "stripe_webhook": Pattern(
        name="stripe_webhook",
        description="Stripe webhook handler with signature verification",
        category="api",
        tags=["stripe", "webhook", "payment", "billing", "subscription"],
        implementation_template=(
            "// Stripe Webhook Handler\n"
            "import Stripe from 'stripe';\n\n"
            "const stripe = new Stripe(process.env.STRIPE_SECRET_KEY!);\n\n"
            "export async function handleWebhook(req: Request): Promise<Response> {\n"
            "  const body = await req.text();\n"
            "  const sig = req.headers.get('stripe-signature')!;\n"
            "  try {\n"
            "    const event = stripe.webhooks.constructEvent(\n"
            "      body, sig, process.env.STRIPE_WEBHOOK_SECRET!\n"
            "    );\n"
            "    switch (event.type) {\n"
            "      case 'checkout.session.completed':\n"
            "        // Handle successful payment\n"
            "        break;\n"
            "      case 'customer.subscription.deleted':\n"
            "        // Handle cancellation\n"
            "        break;\n"
            "    }\n"
            "    return new Response('OK', { status: 200 });\n"
            "  } catch (err) {\n"
            "    return new Response('Webhook Error', { status: 400 });\n"
            "  }\n"
            "}\n"
        ),
        test_template=(
            "describe('Stripe Webhook', () => {\n"
            "  it('rejects invalid signatures', async () => {\n"
            "    const res = await handleWebhook(mockReq);\n"
            "    expect(res.status).toBe(400);\n"
            "  });\n"
            "});\n"
        ),
        anti_patterns=[
            "Not verifying webhook signature",
            "Processing webhook before signature check",
            "Not handling idempotency",
        ],
    ),
    "supabase_realtime": Pattern(
        name="supabase_realtime",
        description="Supabase real-time subscription pattern",
        category="realtime",
        tags=["supabase", "realtime", "websocket", "subscription", "live"],
        implementation_template=(
            "// Supabase Realtime Subscription\n"
            "import { useEffect } from 'react';\n"
            "import { supabase } from '@/lib/supabase';\n\n"
            "export function useRealtimeTable<T>(table: string, callback: (payload: T) => void) {\n"
            "  useEffect(() => {\n"
            "    const channel = supabase.channel(`${table}_changes`)\n"
            "      .on('postgres_changes', { event: '*', schema: 'public', table }, (payload) => {\n"
            "        callback(payload.new as T);\n"
            "      })\n"
            "      .subscribe();\n"
            "    return () => { supabase.removeChannel(channel); };\n"
            "  }, [table, callback]);\n"
            "}\n"
        ),
        test_template=(
            "describe('Supabase Realtime', () => {\n"
            "  it('subscribes and unsubscribes on unmount', () => {\n"
            "    const { unmount } = renderHook(() => useRealtimeTable('todos', vi.fn()));\n"
            "    expect(supabase.channel).toHaveBeenCalledWith('todos_changes');\n"
            "    unmount();\n"
            "    expect(supabase.removeChannel).toHaveBeenCalled();\n"
            "  });\n"
            "});\n"
        ),
        anti_patterns=[
            "Not unsubscribing on component unmount",
            "Creating multiple subscriptions for same table",
        ],
    ),
    "rate_limiting": Pattern(
        name="rate_limiting",
        description="Redis sliding window rate limiter",
        category="infra",
        tags=["rate limit", "redis", "throttle", "api", "security"],
        implementation_template=(
            "// Redis Sliding Window Rate Limiter\n"
            "import Redis from 'ioredis';\n\n"
            "const redis = new Redis(process.env.REDIS_URL!);\n\n"
            "export async function rateLimit(\n"
            "  key: string, limit: number, windowMs: number\n"
            "): Promise<{ allowed: boolean; remaining: number }> {\n"
            "  const now = Date.now();\n"
            "  const windowStart = now - windowMs;\n"
            "  const pipe = redis.pipeline();\n"
            "  pipe.zremrangebyscore(key, 0, windowStart);\n"
            "  pipe.zadd(key, now.toString(), `${now}`);\n"
            "  pipe.zcard(key);\n"
            "  pipe.expire(key, Math.ceil(windowMs / 1000));\n"
            "  const results = await pipe.exec();\n"
            "  const count = (results?.[2]?.[1] as number) ?? 0;\n"
            "  return { allowed: count <= limit, remaining: Math.max(0, limit - count) };\n"
            "}\n"
        ),
        test_template=(
            "describe('Rate Limiter', () => {\n"
            "  it('blocks after limit exceeded', async () => {\n"
            "    for (let i = 0; i < 10; i++) await rateLimit('test', 10, 60000);\n"
            "    const { allowed } = await rateLimit('test', 10, 60000);\n"
            "    expect(allowed).toBe(false);\n"
            "  });\n"
            "});\n"
        ),
        anti_patterns=[
            "Using fixed window instead of sliding window",
            "Not setting TTL on rate limit keys",
        ],
    ),
    "file_upload_s3": Pattern(
        name="file_upload_s3",
        description="S3/R2 file upload with presigned URLs",
        category="api",
        tags=["file upload", "s3", "r2", "presigned", "storage", "upload"],
        implementation_template=(
            "// S3/R2 Presigned Upload\n"
            "import { S3Client, PutObjectCommand } from '@aws-sdk/client-s3';\n"
            "import { getSignedUrl } from '@aws-sdk/s3-request-presigner';\n\n"
            "const s3 = new S3Client({ region: 'auto',\n"
            "  endpoint: process.env.R2_ENDPOINT!,\n"
            "  credentials: { accessKeyId: process.env.R2_KEY!, secretAccessKey: process.env.R2_SECRET! }\n"
            "});\n\n"
            "export async function getUploadUrl(key: string, contentType: string): Promise<string> {\n"
            "  const cmd = new PutObjectCommand({ Bucket: process.env.R2_BUCKET!, Key: key, ContentType: contentType });\n"
            "  return getSignedUrl(s3, cmd, { expiresIn: 3600 });\n"
            "}\n"
        ),
        test_template=(
            "describe('File Upload S3', () => {\n"
            "  it('returns a presigned URL', async () => {\n"
            "    const url = await getUploadUrl('test.png', 'image/png');\n"
            "    expect(url).toContain('X-Amz-Signature');\n"
            "  });\n"
            "});\n"
        ),
        anti_patterns=[
            "Accepting file uploads through API server (use presigned URLs)",
            "Not validating file types and sizes",
            "Hardcoding S3 credentials",
        ],
    ),
    "pagination_cursor": Pattern(
        name="pagination_cursor",
        description="Cursor-based pagination pattern",
        category="data",
        tags=["pagination", "cursor", "infinite scroll", "list", "data"],
        implementation_template=(
            "// Cursor-based Pagination\n"
            "interface PaginatedResponse<T> {\n"
            "  items: T[];\n"
            "  nextCursor: string | null;\n"
            "  hasMore: boolean;\n"
            "}\n\n"
            "export async function fetchPaginated<T>(\n"
            "  table: string, cursor?: string, limit = 20\n"
            "): Promise<PaginatedResponse<T>> {\n"
            "  let query = supabase.from(table).select('*').order('created_at', { ascending: false }).limit(limit + 1);\n"
            "  if (cursor) query = query.lt('created_at', cursor);\n"
            "  const { data } = await query;\n"
            "  const hasMore = (data?.length ?? 0) > limit;\n"
            "  const items = (data?.slice(0, limit) ?? []) as T[];\n"
            "  const nextCursor = hasMore ? items[items.length - 1]?.created_at : null;\n"
            "  return { items, nextCursor, hasMore };\n"
            "}\n"
        ),
        test_template=(
            "describe('Cursor Pagination', () => {\n"
            "  it('returns hasMore when more items exist', async () => {\n"
            "    const result = await fetchPaginated('items', undefined, 2);\n"
            "    expect(result.hasMore).toBeDefined();\n"
            "    expect(result.items.length).toBeLessThanOrEqual(2);\n"
            "  });\n"
            "});\n"
        ),
        anti_patterns=[
            "Using OFFSET-based pagination (O(n) performance)",
            "Not including hasMore flag",
        ],
    ),
    "optimistic_update": Pattern(
        name="optimistic_update",
        description="TanStack Query optimistic update pattern",
        category="state",
        tags=["optimistic", "tanstack", "react query", "mutation", "update"],
        implementation_template=(
            "// TanStack Query Optimistic Update\n"
            "import { useMutation, useQueryClient } from '@tanstack/react-query';\n\n"
            "export function useOptimisticUpdate<T>(queryKey: string[]) {\n"
            "  const queryClient = useQueryClient();\n"
            "  return useMutation({\n"
            "    mutationFn: async (newItem: T) => api.post('/items', newItem),\n"
            "    onMutate: async (newItem) => {\n"
            "      await queryClient.cancelQueries({ queryKey });\n"
            "      const previous = queryClient.getQueryData(queryKey);\n"
            "      queryClient.setQueryData(queryKey, (old: T[]) => [...old, newItem]);\n"
            "      return { previous };\n"
            "    },\n"
            "    onError: (_err, _new, context) => {\n"
            "      queryClient.setQueryData(queryKey, context?.previous);\n"
            "    },\n"
            "    onSettled: () => queryClient.invalidateQueries({ queryKey }),\n"
            "  });\n"
            "}\n"
        ),
        test_template=(
            "describe('Optimistic Update', () => {\n"
            "  it('rolls back on mutation error', async () => {\n"
            "    const { result } = renderHook(() => useOptimisticUpdate(['items']));\n"
            "    await expect(result.current.mutateAsync(bad)).rejects.toThrow();\n"
            "  });\n"
            "});\n"
        ),
        anti_patterns=[
            "Not rolling back on error",
            "Not invalidating queries on settle",
            "Not cancelling in-flight queries before optimistic update",
        ],
    ),
    "error_boundary": Pattern(
        name="error_boundary",
        description="React error boundary with fallback UI",
        category="ui",
        tags=["error boundary", "error", "fallback", "crash", "react"],
        implementation_template=(
            "// React Error Boundary\n"
            "import { Component, ErrorInfo, ReactNode } from 'react';\n\n"
            "interface Props { children: ReactNode; fallback?: ReactNode; }\n"
            "interface State { hasError: boolean; error?: Error; }\n\n"
            "export class ErrorBoundary extends Component<Props, State> {\n"
            "  state: State = { hasError: false };\n"
            "  static getDerivedStateFromError(error: Error): State {\n"
            "    return { hasError: true, error };\n"
            "  }\n"
            "  componentDidCatch(error: Error, info: ErrorInfo) {\n"
            "    console.error('ErrorBoundary caught:', error, info);\n"
            "  }\n"
            "  render() {\n"
            "    if (this.state.hasError) {\n"
            "      return this.props.fallback ?? <div>Something went wrong.</div>;\n"
            "    }\n"
            "    return this.props.children;\n"
            "  }\n"
            "}\n"
        ),
        test_template=(
            "describe('ErrorBoundary', () => {\n"
            "  it('renders fallback on child error', () => {\n"
            "    const ThrowError = () => { throw new Error('test'); };\n"
            "    render(<ErrorBoundary fallback={<div>Error</div>}><ThrowError /></ErrorBoundary>);\n"
            "    expect(screen.getByText('Error')).toBeInTheDocument();\n"
            "  });\n"
            "});\n"
        ),
        anti_patterns=[
            "Using try/catch for render errors (won't work)",
            "Not logging errors in componentDidCatch",
        ],
    ),
    "zustand_store": Pattern(
        name="zustand_store",
        description="Zustand store with immer middleware",
        category="state",
        tags=["zustand", "store", "state management", "immer", "global state"],
        implementation_template=(
            "// Zustand Store with Immer\n"
            "import { create } from 'zustand';\n"
            "import { immer } from 'zustand/middleware/immer';\n\n"
            "interface AppState {\n"
            "  items: Item[];\n"
            "  addItem: (item: Item) => void;\n"
            "  removeItem: (id: string) => void;\n"
            "}\n\n"
            "export const useAppStore = create<AppState>()(immer((set) => ({\n"
            "  items: [],\n"
            "  addItem: (item) => set((state) => { state.items.push(item); }),\n"
            "  removeItem: (id) => set((state) => {\n"
            "    state.items = state.items.filter((i) => i.id !== id);\n"
            "  }),\n"
            "})));\n"
        ),
        test_template=(
            "describe('Zustand Store', () => {\n"
            "  it('adds and removes items immutably', () => {\n"
            "    const { addItem, removeItem } = useAppStore.getState();\n"
            "    addItem({ id: '1', name: 'Test' });\n"
            "    expect(useAppStore.getState().items).toHaveLength(1);\n"
            "    removeItem('1');\n"
            "    expect(useAppStore.getState().items).toHaveLength(0);\n"
            "  });\n"
            "});\n"
        ),
        anti_patterns=[
            "Mutating state directly without immer",
            "Using useState for global state",
            "Not using selectors for derived state",
        ],
    ),
    "tanstack_query": Pattern(
        name="tanstack_query",
        description="TanStack Query v5 data fetching with optimistic updates",
        category="data",
        tags=["tanstack", "react query", "data fetching", "cache", "query"],
        implementation_template=(
            "// TanStack Query v5 Pattern\n"
            "import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';\n"
            "import { api } from '@/lib/api';\n\n"
            "export function useItems() {\n"
            "  return useQuery({\n"
            "    queryKey: ['items'],\n"
            "    queryFn: () => api.get<Item[]>('/items').then(r => r.data),\n"
            "    staleTime: 5 * 60 * 1000,\n"
            "  });\n"
            "}\n"
        ),
        test_template="",
        anti_patterns=[
            "Fetching data in useEffect instead of useQuery",
            "Not setting staleTime",
        ],
    ),
    "form_validation": Pattern(
        name="form_validation",
        description="React Hook Form + Zod validation pattern",
        category="form",
        tags=["form", "validation", "zod", "react hook form", "input"],
        implementation_template=(
            "// React Hook Form + Zod\n"
            "import { useForm } from 'react-hook-form';\n"
            "import { zodResolver } from '@hookform/resolvers/zod';\n"
            "import { z } from 'zod';\n\n"
            "const schema = z.object({\n"
            "  email: z.string().email(),\n"
            "  password: z.string().min(8),\n"
            "});\n\n"
            "type FormData = z.infer<typeof schema>;\n\n"
            "export function LoginForm() {\n"
            "  const { register, handleSubmit, formState: { errors } } = useForm<FormData>({\n"
            "    resolver: zodResolver(schema),\n"
            "  });\n"
            "  const onSubmit = (data: FormData) => console.log(data);\n"
            "  return <form onSubmit={handleSubmit(onSubmit)}>...</form>;\n"
            "}\n"
        ),
        test_template=(
            "describe('Form Validation', () => {\n"
            "  it('rejects invalid email', () => {\n"
            "    const result = schema.safeParse({ email: 'bad', password: '12345678' });\n"
            "    expect(result.success).toBe(false);\n"
            "  });\n"
            "  it('accepts valid input', () => {\n"
            "    const result = schema.safeParse({ email: 'a@b.com', password: '12345678' });\n"
            "    expect(result.success).toBe(true);\n"
            "  });\n"
            "});\n"
        ),
        anti_patterns=[
            "Manual validation instead of schema-based",
            "Not displaying field errors",
        ],
    ),
    # Additional patterns for broader coverage
    "crud_api": Pattern(
        name="crud_api",
        description="RESTful CRUD API endpoints pattern",
        category="api",
        tags=["crud", "rest", "api", "endpoints", "resource"],
        implementation_template="// CRUD API pattern",
        test_template="",
        anti_patterns=["Not returning proper HTTP status codes"],
    ),
    "websocket_handler": Pattern(
        name="websocket_handler",
        description="WebSocket connection handler with heartbeat",
        category="realtime",
        tags=["websocket", "ws", "realtime", "connection", "live"],
        implementation_template="// WebSocket handler pattern",
        test_template="",
        anti_patterns=["Not implementing reconnection logic"],
    ),
    "image_optimization": Pattern(
        name="image_optimization",
        description="Next.js Image component with optimization",
        category="ui",
        tags=["image", "optimization", "lazy load", "responsive"],
        implementation_template="// Image optimization pattern",
        test_template="",
        anti_patterns=["Using plain img tags without optimization"],
    ),
    "dark_mode": Pattern(
        name="dark_mode",
        description="Dark mode toggle with system preference detection",
        category="ui",
        tags=["dark mode", "theme", "toggle", "appearance", "light"],
        implementation_template="// Dark mode pattern",
        test_template="",
        anti_patterns=["Not respecting system color scheme preference"],
    ),
    "infinite_scroll": Pattern(
        name="infinite_scroll",
        description="Infinite scroll with intersection observer",
        category="ui",
        tags=["infinite scroll", "pagination", "scroll", "load more"],
        implementation_template="// Infinite scroll pattern",
        test_template="",
        anti_patterns=["Using scroll event listener instead of IntersectionObserver"],
    ),
    "toast_notification": Pattern(
        name="toast_notification",
        description="Toast notification system with queue",
        category="ui",
        tags=["toast", "notification", "alert", "message", "feedback"],
        implementation_template="// Toast notification pattern",
        test_template="",
        anti_patterns=["Not auto-dismissing toasts"],
    ),
    "protected_route": Pattern(
        name="protected_route",
        description="Protected route with auth redirect",
        category="auth",
        tags=["protected", "route", "guard", "auth", "redirect", "private"],
        implementation_template="// Protected route pattern",
        test_template="",
        anti_patterns=["Not redirecting to login on auth failure"],
    ),
    "env_validation": Pattern(
        name="env_validation",
        description="Environment variable validation at startup",
        category="infra",
        tags=["env", "environment", "config", "validation", "startup"],
        implementation_template="// Env validation pattern",
        test_template="",
        anti_patterns=["Accessing env vars without validation"],
    ),
    "api_client": Pattern(
        name="api_client",
        description="Axios API client with interceptors",
        category="api",
        tags=["api", "client", "axios", "http", "request", "interceptor"],
        implementation_template="// API client pattern",
        test_template="",
        anti_patterns=["Not using request/response interceptors"],
    ),
    "database_migration": Pattern(
        name="database_migration",
        description="Database migration with rollback support",
        category="data",
        tags=["database", "migration", "schema", "sql", "rollback"],
        implementation_template="// Database migration pattern",
        test_template="",
        anti_patterns=["Running migrations without rollback plan"],
    ),
    "caching_strategy": Pattern(
        name="caching_strategy",
        description="Multi-layer caching with Redis and in-memory",
        category="infra",
        tags=["cache", "caching", "redis", "memory", "performance"],
        implementation_template="// Caching strategy pattern",
        test_template="",
        anti_patterns=["Not invalidating cache on data changes"],
    ),
    "search_filter": Pattern(
        name="search_filter",
        description="Search and filter with debounced input",
        category="ui",
        tags=["search", "filter", "debounce", "input", "query"],
        implementation_template="// Search filter pattern",
        test_template="",
        anti_patterns=["Not debouncing search input"],
    ),
    "modal_dialog": Pattern(
        name="modal_dialog",
        description="Accessible modal dialog with focus trap",
        category="ui",
        tags=["modal", "dialog", "popup", "overlay", "accessible"],
        implementation_template="// Modal dialog pattern",
        test_template="",
        anti_patterns=["Not trapping focus inside modal"],
    ),
    "responsive_layout": Pattern(
        name="responsive_layout",
        description="Responsive layout with mobile-first breakpoints",
        category="ui",
        tags=["responsive", "layout", "mobile", "breakpoint", "grid"],
        implementation_template="// Responsive layout pattern",
        test_template="",
        anti_patterns=["Using fixed widths instead of responsive units"],
    ),
    "loading_skeleton": Pattern(
        name="loading_skeleton",
        description="Loading skeleton placeholder components",
        category="ui",
        tags=["loading", "skeleton", "placeholder", "shimmer"],
        implementation_template="// Loading skeleton pattern",
        test_template="",
        anti_patterns=["Using spinners for content loading"],
    ),
    "email_service": Pattern(
        name="email_service",
        description="Transactional email with templates",
        category="api",
        tags=["email", "notification", "template", "sendgrid", "ses"],
        implementation_template="// Email service pattern",
        test_template="",
        anti_patterns=["Sending emails synchronously in request handlers"],
    ),
    "logging_service": Pattern(
        name="logging_service",
        description="Structured logging with context propagation",
        category="infra",
        tags=["logging", "log", "monitoring", "debug", "structured"],
        implementation_template="// Logging service pattern",
        test_template="",
        anti_patterns=["Using console.log in production"],
    ),
    "file_download": Pattern(
        name="file_download",
        description="File download with streaming response",
        category="api",
        tags=["file", "download", "stream", "export", "csv"],
        implementation_template="// File download pattern",
        test_template="",
        anti_patterns=["Loading entire file into memory before sending"],
    ),
    "data_table": Pattern(
        name="data_table",
        description="Sortable, filterable data table component",
        category="ui",
        tags=["table", "data", "sort", "filter", "grid", "list"],
        implementation_template="// Data table pattern",
        test_template="",
        anti_patterns=["Not virtualizing large lists"],
    ),
}


# ── Public API ───────────────────────────────────────────────────────


def get_pattern(name: str) -> Pattern | None:
    """Get a pattern by its exact name.

    Args:
        name: Exact pattern name (e.g., 'auth_jwt').

    Returns:
        Pattern if found, None otherwise.
    """
    return _PATTERN_REGISTRY.get(name)


def find_applicable_patterns(feature_description: str) -> list[Pattern]:
    """Find patterns applicable to a feature description.

    Uses keyword matching against pattern tags, names, and descriptions.

    Args:
        feature_description: Natural language description of a feature
            (e.g., "user authentication with social login").

    Returns:
        List of matching patterns, sorted by relevance (most matches first).
    """
    if not feature_description:
        return []

    # Normalize input
    words = set(re.findall(r"\w+", feature_description.lower()))

    scored: list[tuple[int, Pattern]] = []

    for pattern in _PATTERN_REGISTRY.values():
        score = 0

        # Check tag matches (highest weight)
        for tag in pattern.tags:
            tag_words = set(tag.lower().split())
            matches = words & tag_words
            score += len(matches) * 3

        # Check name match
        name_words = set(pattern.name.lower().replace("_", " ").split())
        score += len(words & name_words) * 2

        # Check description match
        desc_words = set(re.findall(r"\w+", pattern.description.lower()))
        score += len(words & desc_words)

        if score > 0:
            scored.append((score, pattern))

    # Sort by score descending
    scored.sort(key=lambda x: x[0], reverse=True)

    result = [pattern for _, pattern in scored]

    logger.info(
        "pattern_library.search",
        query=feature_description,
        results_count=len(result),
        top_matches=[p.name for p in result[:5]],
    )

    return result

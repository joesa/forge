# FORGE — Master Agent Context

## What This Project Is
FORGE is an AI-native full-stack application development platform.
Users arrive with an idea and leave with a live production application.
Guarantee: zero broken first builds through a 10-layer reliability
architecture and a live preview system.

## Technology Stack

### Backend
- Python 3.12, FastAPI (fully async), PostgreSQL 16 (Nhost)
- PgBouncer (transaction mode, 1000 conns), 2x read replicas
- SQLAlchemy 2.0 async, Alembic, Upstash Redis, Pinecone, Cloudflare R2
- Nhost Auth (JWT/JWKS), AES-256-GCM encryption
- LangGraph, Trigger.dev, BullMQ, OpenTelemetry, Sentry

### Frontend
- React 18, Vite 5, TypeScript 5.4 strict, React Router v6
- Zustand, TanStack Query v5, Monaco Editor, xterm.js
- Tailwind CSS v3, Framer Motion, React Hook Form + Zod, Axios
- Cloudflare Pages

### Infrastructure
- Northflank microVM containers (backend)
- Northflank Firecracker VMs (sandboxes, pre-warmed pool 20+)
- Cloudflare Worker at *.preview.forge.dev (preview proxy)
- Cloudflare Durable Objects (HMR relay + WebSocket state)
- Cloudflare KV (sandbox URL registry)

## Architecture Rules — NEVER Violate

1. DB reads → replica session ONLY (get_read_session)
2. DB writes → primary session ONLY (get_write_session)
3. All user API keys: AES-256-GCM encrypted, IV stored separately
4. Build agents: temperature=0, fixed seed (deterministic)
5. File coherence engine runs AFTER all 10 build agents — not per-agent
6. Schema injection happens BEFORE each relevant agent starts
7. Never call real external APIs in tests — Wiremock stubs only
8. Never hardcode secrets — always from environment variables
9. TypeScript: strict mode, zero 'any' types
10. Preview system target: file save → browser update under 700ms

## Standard Commands
  cd backend && uvicorn app.main:app --reload
  cd backend && pytest tests/ -v
  cd backend && alembic upgrade head
  cd frontend && npm run dev
  cd frontend && npm run typecheck
  cd frontend && npm run lint

## Build Status (update as you progress)
Phase: 1 — Foundation
Completed: Session 1.1 — Backend project setup
Completed: Session 1.2 — Database models & Alembic migrations
Completed: Session 1.3 — Auth API & Projects API
Completed: Session 1.4 — Frontend scaffold (React + Vite + TypeScript + Tailwind + design system)
Next: Session 1.5 — Frontend pages & components
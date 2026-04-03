# FORGE — Master Agent Context

## What This Project Is
FORGE is an AI-native full-stack application development platform.
Users arrive with an idea and leave with a live production application.
Guarantee: zero broken first builds through a 10-layer reliability
architecture and a live preview system.

## Technology Stack

### Backend
- Python 3.12, FastAPI (async), PostgreSQL 16 (Northflank managed addon)
- Nhost: JWT auth only — JWKS validation, no database hosting
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
Completed: Session 1.5 — LangGraph pipeline orchestration layer (6-stage graph, 12 gates, API + WebSocket)
Completed: Session 1.6 — C-Suite executive agents (8 agents, G3 resolver, synthesizer, G4 coherence)
Completed: Session 1.7 — Reliability Layers 1, 2, 4 (pre-generation contracts, schema-driven generation, file coherence engine)
Completed: Session 1.7b — Reliability Layers 3, 5, 6 (static analysis, code contracts, build intelligence)
Completed: Session 1.7c — Reliability Layer 7 (Wiremock external service simulation, 6 service stubs)
Completed: Session 1.7d — Reliability Layer 8 (post-build verification: visual regression, SAST, perf, a11y, dead code, seeds)
Completed: Session 1.7e — Reliability Layers 9, 10 (hotfix agent, rollback engine, canary deploy, migration safety, context window mgr, CSS validator, determinism enforcer, fallback cascade)
Completed: Session 1.8p — Preview system backend (preview URL, health, screenshots, shares, snapshots, annotations, file sync, WebSocket console)
Completed: Session 1.8t — Trigger.dev durable jobs (pipeline-run, build-run, idea-generation, sandbox-lifecycle, pool-replenish, internal API, pipeline service)
Next: Session 1.8 — Frontend pages & components

<!-- TRIGGER.DEV basic START -->
# Trigger.dev Basic Tasks (v4)

**MUST use `@trigger.dev/sdk`, NEVER `client.defineJob`**

## Basic Task

```ts
import { task } from "@trigger.dev/sdk";

export const processData = task({
  id: "process-data",
  retry: {
    maxAttempts: 10,
    factor: 1.8,
    minTimeoutInMs: 500,
    maxTimeoutInMs: 30_000,
    randomize: false,
  },
  run: async (payload: { userId: string; data: any[] }) => {
    // Task logic - runs for long time, no timeouts
    console.log(`Processing ${payload.data.length} items for user ${payload.userId}`);
    return { processed: payload.data.length };
  },
});
```

## Schema Task (with validation)

```ts
import { schemaTask } from "@trigger.dev/sdk";
import { z } from "zod";

export const validatedTask = schemaTask({
  id: "validated-task",
  schema: z.object({
    name: z.string(),
    age: z.number(),
    email: z.string().email(),
  }),
  run: async (payload) => {
    // Payload is automatically validated and typed
    return { message: `Hello ${payload.name}, age ${payload.age}` };
  },
});
```

## Triggering Tasks

### From Backend Code

```ts
import { tasks } from "@trigger.dev/sdk";
import type { processData } from "./trigger/tasks";

// Single trigger
const handle = await tasks.trigger<typeof processData>("process-data", {
  userId: "123",
  data: [{ id: 1 }, { id: 2 }],
});

// Batch trigger (up to 1,000 items, 3MB per payload)
const batchHandle = await tasks.batchTrigger<typeof processData>("process-data", [
  { payload: { userId: "123", data: [{ id: 1 }] } },
  { payload: { userId: "456", data: [{ id: 2 }] } },
]);
```

### Debounced Triggering

Consolidate multiple triggers into a single execution:

```ts
// Multiple rapid triggers with same key = single execution
await myTask.trigger(
  { userId: "123" },
  {
    debounce: {
      key: "user-123-update",  // Unique key for debounce group
      delay: "5s",              // Wait before executing
    },
  }
);

// Trailing mode: use payload from LAST trigger
await myTask.trigger(
  { data: "latest-value" },
  {
    debounce: {
      key: "trailing-example",
      delay: "10s",
      mode: "trailing",  // Default is "leading" (first payload)
    },
  }
);
```

**Debounce modes:**
- `leading` (default): Uses payload from first trigger, subsequent triggers only reschedule
- `trailing`: Uses payload from most recent trigger

### From Inside Tasks (with Result handling)

```ts
export const parentTask = task({
  id: "parent-task",
  run: async (payload) => {
    // Trigger and continue
    const handle = await childTask.trigger({ data: "value" });

    // Trigger and wait - returns Result object, NOT task output
    const result = await childTask.triggerAndWait({ data: "value" });
    if (result.ok) {
      console.log("Task output:", result.output); // Actual task return value
    } else {
      console.error("Task failed:", result.error);
    }

    // Quick unwrap (throws on error)
    const output = await childTask.triggerAndWait({ data: "value" }).unwrap();

    // Batch trigger and wait
    const results = await childTask.batchTriggerAndWait([
      { payload: { data: "item1" } },
      { payload: { data: "item2" } },
    ]);

    for (const run of results) {
      if (run.ok) {
        console.log("Success:", run.output);
      } else {
        console.log("Failed:", run.error);
      }
    }
  },
});

export const childTask = task({
  id: "child-task",
  run: async (payload: { data: string }) => {
    return { processed: payload.data };
  },
});
```

> Never wrap triggerAndWait or batchTriggerAndWait calls in a Promise.all or Promise.allSettled as this is not supported in Trigger.dev tasks.

## Waits

```ts
import { task, wait } from "@trigger.dev/sdk";

export const taskWithWaits = task({
  id: "task-with-waits",
  run: async (payload) => {
    console.log("Starting task");

    // Wait for specific duration
    await wait.for({ seconds: 30 });
    await wait.for({ minutes: 5 });
    await wait.for({ hours: 1 });
    await wait.for({ days: 1 });

    // Wait until specific date
    await wait.until({ date: new Date("2024-12-25") });

    // Wait for token (from external system)
    await wait.forToken({
      token: "user-approval-token",
      timeoutInSeconds: 3600, // 1 hour timeout
    });

    console.log("All waits completed");
    return { status: "completed" };
  },
});
```

> Never wrap wait calls in a Promise.all or Promise.allSettled as this is not supported in Trigger.dev tasks.

## Key Points

- **Result vs Output**: `triggerAndWait()` returns a `Result` object with `ok`, `output`, `error` properties - NOT the direct task output
- **Type safety**: Use `import type` for task references when triggering from backend
- **Waits > 5 seconds**: Automatically checkpointed, don't count toward compute usage
- **Debounce + idempotency**: Idempotency keys take precedence over debounce settings

## NEVER Use (v2 deprecated)

```ts
// BREAKS APPLICATION
client.defineJob({
  id: "job-id",
  run: async (payload, io) => {
    /* ... */
  },
});
```

Use SDK (`@trigger.dev/sdk`), check `result.ok` before accessing `result.output`

<!-- TRIGGER.DEV basic END -->
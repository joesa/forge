"""
FORGE Reliability Architecture — 10-layer system for zero broken first builds.

Layers implemented:
  1. Pre-generation contracts (dependency resolution, env validation)
  2. Schema-driven generation (OpenAPI, Zod, Pydantic, DB types)
  3. Static analysis (AST analyser, import graph resolver, runtime error predictor)
  4. File coherence engine (import/export validation, seam detection)
  5. Code contract enforcement (pattern library, API contract validator, type inference)
  6. Build intelligence (semantic cache, build memory, error boundaries, incremental builds)
  7. External service simulation (Wiremock stubs — never hit real APIs in tests)
  8. Post-build verification (visual regression, SAST, perf, a11y, dead code, seeds)
  9. Resilience and recovery (hotfix agent, rollback engine, canary deploy, migration safety)
  10. AI agent reliability (context window manager, CSS validator, determinism enforcer, fallback cascade)
"""

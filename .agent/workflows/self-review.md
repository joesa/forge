---
description: 
---

# Workflow: Self-Review

Trigger: "run self-review"

Steps:
1. Read AGENTS.md and verify every file matches the architecture
2. Check DB read/write split is correct
3. Check no secrets are hardcoded
4. Check every route verifies user ownership
5. Run: cd backend && pytest tests/ -v — fix all failures
6. Run: cd frontend && npm run typecheck — fix all errors
7. Run: cd frontend && npm run lint — fix all warnings
8. Report: list every issue found and confirm it was fixed
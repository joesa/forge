---
trigger: always_on
---

---
alwaysApply: true
---

# Core Rules — Active on Every Task

Read AGENTS.md before starting any task.

NEVER:
- Hardcode secrets, passwords, or API keys
- Use 'any' type in TypeScript
- Call real external APIs in tests (use Wiremock)
- Forget to run tests after making changes
- Skip the self-review step

ALWAYS:
- Run: cd backend && pytest tests/ -v after backend changes
- Run: cd frontend && npm run typecheck after frontend changes
- Fix all failures before reporting the task complete
- After completing work, silently self-review for:
  * Unhandled error cases (network failures, null values, DB down)
  * Missing auth/ownership checks on API routes
  * Security issues (injection, XSS, path traversal)
  * Architecture violations from AGENTS.md
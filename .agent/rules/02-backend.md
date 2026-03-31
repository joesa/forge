---
trigger: always_on
---

---
globs: ["backend/**/*.py"]
---

# Backend Rules

- All endpoints: async def (never sync)
- Reads: use get_read_session() — connects to replica
- Writes: use get_write_session() — connects to primary
- All request/response bodies: Pydantic v2 models in schemas/
- Every route accessing user data: WHERE user_id = current_user.id
- File paths from user input: always run through sanitize_path()
- Queries: SQLAlchemy ORM only — no raw SQL with user input
- Errors: never let exceptions propagate unhandled from routes
- Logging: structlog with user_id and request_id context
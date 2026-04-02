#!/usr/bin/env python3
"""
FORGE — Local development preflight check.

Run this script to verify that all local services are configured and
reachable before starting the dev server or running tests.

Usage:
    python scripts/check_local_services.py

Exit codes:
    0 — All services OK
    1 — One or more services failed
"""

from __future__ import annotations

import asyncio
import os
import sys

# Ensure we load from the backend .env
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _print_ok(label: str, detail: str = "") -> None:
    print(f"  ✅  {label}{f' — {detail}' if detail else ''}")


def _print_fail(label: str, detail: str = "") -> None:
    print(f"  ❌  {label}{f' — {detail}' if detail else ''}")


def _print_warn(label: str, detail: str = "") -> None:
    print(f"  ⚠️  {label}{f' — {detail}' if detail else ''}")


async def check_postgres() -> bool:
    """Verify PostgreSQL is reachable with the configured credentials."""
    try:
        import asyncpg
    except ImportError:
        _print_fail("PostgreSQL", "asyncpg not installed")
        return False

    db_url = os.environ.get("DATABASE_URL", "")
    if not db_url:
        # Try loading from .env
        try:
            from dotenv import dotenv_values
            env = dotenv_values(".env")
            db_url = env.get("DATABASE_URL", "")
        except ImportError:
            pass

    if not db_url:
        _print_fail("PostgreSQL", "DATABASE_URL not set in .env")
        return False

    # Convert SQLAlchemy URL to asyncpg format
    dsn = db_url.replace("postgresql+asyncpg://", "postgresql://")

    try:
        conn = await asyncio.wait_for(
            asyncpg.connect(dsn, timeout=5),
            timeout=8.0,
        )
        version = await conn.fetchval("SELECT version()")
        tables = await conn.fetchval(
            "SELECT count(*) FROM pg_tables WHERE schemaname='public'"
        )
        await conn.close()

        short_ver = version.split(",")[0] if version else "unknown"
        _print_ok("PostgreSQL", f"{short_ver}, {tables} tables")
        return True
    except asyncio.TimeoutError:
        _print_fail("PostgreSQL", "Connection timed out (check if DB is running)")
        return False
    except Exception as e:
        _print_fail("PostgreSQL", str(e))
        return False


async def check_redis() -> bool:
    """Verify Redis is reachable."""
    try:
        import redis.asyncio as aioredis
    except ImportError:
        _print_fail("Redis", "redis[asyncio] not installed")
        return False

    redis_url = os.environ.get("REDIS_URL", "")
    if not redis_url:
        try:
            from dotenv import dotenv_values
            env = dotenv_values(".env")
            redis_url = env.get("REDIS_URL", "redis://127.0.0.1:6379")
        except ImportError:
            redis_url = "redis://127.0.0.1:6379"

    # Warn if pointing at Upstash
    if "upstash" in redis_url or "fly-" in redis_url:
        _print_warn(
            "Redis",
            "REDIS_URL points to Upstash/Fly.io — this will hang locally! "
            "Use redis://127.0.0.1:6379 for development.",
        )
        return False

    try:
        r = aioredis.from_url(
            redis_url,
            decode_responses=True,
            socket_connect_timeout=3,
            socket_timeout=3,
        )
        pong = await asyncio.wait_for(r.ping(), timeout=5.0)
        info = await r.info("server")
        version = info.get("redis_version", "unknown")
        await r.aclose()

        if pong:
            _print_ok("Redis", f"v{version} at {redis_url}")
            return True
        else:
            _print_fail("Redis", "PING returned False")
            return False
    except asyncio.TimeoutError:
        _print_fail("Redis", f"Connection timed out at {redis_url}")
        return False
    except Exception as e:
        _print_fail("Redis", str(e))
        return False


def check_env_file() -> bool:
    """Verify .env exists and has the critical keys uncommented."""
    env_path = ".env"
    if not os.path.exists(env_path):
        _print_fail(".env file", "File not found — copy .env.example to .env")
        return False

    with open(env_path) as f:
        content = f.read()

    issues: list[str] = []

    # Check critical keys are present and uncommented
    critical_keys = ["DATABASE_URL", "DATABASE_READ_URL", "REDIS_URL"]
    for key in critical_keys:
        # Match lines that start with the key (not commented)
        lines = [
            line for line in content.splitlines()
            if line.strip().startswith(f"{key}=")
        ]
        if not lines:
            issues.append(f"{key} is missing or commented out")

    # Check for dangerous patterns
    if "upstash" in content.split("#")[0] if "#" not in content else "":
        pass  # Complex check — skip
    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        if "upstash" in stripped.lower() and "REDIS_URL" in stripped:
            issues.append(
                "REDIS_URL points to Upstash — use redis://127.0.0.1:6379"
            )
        if "localhost" in stripped and (
            "DATABASE_URL" in stripped or "DATABASE_READ_URL" in stripped
        ):
            issues.append(
                f"Use 127.0.0.1 instead of localhost in {stripped.split('=')[0]} "
                "(avoids asyncpg IPv6 hangs)"
            )

    if issues:
        _print_fail(".env file", "; ".join(issues))
        return False

    _print_ok(".env file", "All critical keys present")
    return True


def check_conftest() -> bool:
    """Verify tests/conftest.py uses local services."""
    conftest_path = "tests/conftest.py"
    if not os.path.exists(conftest_path):
        _print_warn("conftest.py", "Not found — tests may not be configured")
        return True

    with open(conftest_path) as f:
        content = f.read()

    issues: list[str] = []

    for line in content.splitlines():
        stripped = line.strip()
        # Skip comments — they may contain warnings about Upstash which is fine
        if stripped.startswith("#") or not stripped:
            continue
        # Flag active REDIS_URL pointing to external services
        if "REDIS_URL" in stripped and ("upstash" in stripped.lower() or "fly-" in stripped.lower()):
            issues.append("REDIS_URL in conftest points to Upstash/Fly.io — use redis://localhost:6379")
        # Flag active DATABASE_URL pointing to external services
        if ("DATABASE_URL" in stripped or "DATABASE_READ_URL" in stripped):
            if "addon.code.run" in stripped or "nhost" in stripped.lower():
                issues.append(f"DB URL in conftest points to remote service — use 127.0.0.1")


    if issues:
        _print_fail("conftest.py", "; ".join(issues))
        return False

    _print_ok("conftest.py", "Uses local services for tests")
    return True


async def main() -> int:
    print()
    print("🔧 FORGE — Local Development Preflight Check")
    print("=" * 50)
    print()

    results: list[bool] = []

    # 1. Check .env file
    print("📄 Configuration:")
    results.append(check_env_file())
    results.append(check_conftest())
    print()

    # 2. Check PostgreSQL
    print("🐘 PostgreSQL:")
    results.append(await check_postgres())
    print()

    # 3. Check Redis
    print("🔴 Redis:")
    results.append(await check_redis())
    print()

    # Summary
    print("=" * 50)
    passed = sum(results)
    total = len(results)
    if all(results):
        print(f"✅ All {total} checks passed — ready for development!")
        return 0
    else:
        failed = total - passed
        print(f"❌ {failed}/{total} checks failed — fix the issues above.")
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

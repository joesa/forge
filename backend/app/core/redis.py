"""
Upstash Redis async client utilities.

Provides cache helpers (get / set / delete) and a pub/sub publisher.
"""

import json
from typing import Any

import redis.asyncio as aioredis

from app.config import settings

# ── Connection pool (lazy singleton) ─────────────────────────────────
_pool: aioredis.Redis | None = None


async def get_redis() -> aioredis.Redis:
    """Return (and lazily create) the shared async Redis client."""
    global _pool  # noqa: PLW0603
    if _pool is None:
        _pool = aioredis.from_url(
            settings.REDIS_URL,
            decode_responses=True,
            max_connections=20,
        )
    return _pool


async def close_redis() -> None:
    """Close the Redis connection pool (call on app shutdown)."""
    global _pool  # noqa: PLW0603
    if _pool is not None:
        await _pool.close()
        _pool = None


# ── Cache helpers ────────────────────────────────────────────────────
async def get_cache(key: str) -> str | None:
    """Fetch a cached value by key. Returns ``None`` on miss."""
    client = await get_redis()
    return await client.get(key)


async def set_cache(key: str, value: str, ttl_seconds: int = 3600) -> None:
    """Store a value in cache with a TTL (default 1 hour)."""
    client = await get_redis()
    await client.set(key, value, ex=ttl_seconds)


async def delete_cache(key: str) -> None:
    """Remove a key from the cache."""
    client = await get_redis()
    await client.delete(key)


# ── Pub/sub ──────────────────────────────────────────────────────────
async def publish_event(channel: str, data: dict[str, Any]) -> None:
    """Publish a JSON-serialised event on *channel*."""
    client = await get_redis()
    await client.publish(channel, json.dumps(data))

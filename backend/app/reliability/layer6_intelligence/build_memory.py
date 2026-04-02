"""
Layer 6 — Build memory.

Stores successful build patterns for future reference.
Used by scaffold_agent to learn from past successful builds.

Storage: Redis (Upstash) with JSON serialization.
"""

from __future__ import annotations

import json
import time

from pydantic import BaseModel, Field

import structlog

from app.config import settings

logger = structlog.get_logger(__name__)

# Redis key prefix for build memories
_MEMORY_PREFIX = "forge:build_memory:"
_MEMORY_INDEX_KEY = "forge:build_memory:index"
_MAX_MEMORIES = 500  # Maximum stored memories


class BuildMemory(BaseModel):
    """A single build memory record."""

    build_id: str
    tech_stack: list[str] = Field(default_factory=list)
    patterns_used: list[str] = Field(default_factory=list)
    errors_fixed: list[str] = Field(default_factory=list)
    features: list[str] = Field(default_factory=list)
    build_duration_seconds: float = 0.0
    success: bool = True
    recorded_at: str = ""


def _get_redis_client():
    """Get Redis client instance."""
    import redis

    return redis.from_url(
        settings.REDIS_URL,
        decode_responses=True,
    )


async def record_successful_build(
    build_id: str,
    tech_stack: list[str],
    patterns_used: list[str],
    errors_fixed: list[str],
    features: list[str] | None = None,
    build_duration_seconds: float = 0.0,
) -> bool:
    """Record a successful build for future reference.

    Args:
        build_id: Unique build identifier.
        tech_stack: List of technologies used.
        patterns_used: List of pattern names applied.
        errors_fixed: List of errors that were fixed during build.
        features: List of features implemented.
        build_duration_seconds: How long the build took.

    Returns:
        True if recorded successfully, False otherwise.
    """
    try:
        memory = BuildMemory(
            build_id=build_id,
            tech_stack=tech_stack,
            patterns_used=patterns_used,
            errors_fixed=errors_fixed,
            features=features or [],
            build_duration_seconds=build_duration_seconds,
            success=True,
            recorded_at=time.strftime(
                "%Y-%m-%dT%H:%M:%SZ", time.gmtime()
            ),
        )

        client = _get_redis_client()
        memory_key = f"{_MEMORY_PREFIX}{build_id}"

        # Store the memory
        client.set(
            memory_key,
            memory.model_dump_json(),
            ex=60 * 60 * 24 * 90,  # 90 day TTL
        )

        # Add to index (sorted set by timestamp)
        client.zadd(
            _MEMORY_INDEX_KEY,
            {build_id: time.time()},
        )

        # Trim index to max size
        index_size = client.zcard(_MEMORY_INDEX_KEY)
        if index_size > _MAX_MEMORIES:
            # Remove oldest entries
            excess = index_size - _MAX_MEMORIES
            oldest = client.zrange(_MEMORY_INDEX_KEY, 0, excess - 1)
            if oldest:
                pipe = client.pipeline()
                for old_id in oldest:
                    pipe.delete(f"{_MEMORY_PREFIX}{old_id}")
                pipe.zremrangebyrank(_MEMORY_INDEX_KEY, 0, excess - 1)
                pipe.execute()

        logger.info(
            "build_memory.recorded",
            build_id=build_id,
            tech_stack=tech_stack,
            patterns_count=len(patterns_used),
        )
        return True

    except Exception as e:
        logger.warning(
            "build_memory.record_failed",
            build_id=build_id,
            error=str(e),
        )
        return False


async def get_relevant_memories(
    tech_stack: list[str],
    features: list[str] | None = None,
    limit: int = 10,
) -> list[BuildMemory]:
    """Retrieve relevant build memories for a given tech stack and features.

    Uses keyword matching to find memories with similar tech stacks and features.

    Args:
        tech_stack: List of technologies to match.
        features: Optional list of features to match.
        limit: Maximum number of memories to return.

    Returns:
        List of relevant BuildMemory records, sorted by relevance.
    """
    try:
        client = _get_redis_client()

        # Get all memory IDs from index (most recent first)
        all_ids = client.zrevrange(_MEMORY_INDEX_KEY, 0, -1)

        if not all_ids:
            return []

        # Fetch all memories
        memories: list[tuple[int, BuildMemory]] = []
        tech_set = set(t.lower() for t in tech_stack)
        feature_set = set(f.lower() for f in (features or []))

        for memory_id in all_ids:
            raw = client.get(f"{_MEMORY_PREFIX}{memory_id}")
            if not raw:
                continue

            try:
                memory = BuildMemory.model_validate_json(raw)
            except Exception:
                continue

            # Score by tech stack overlap
            memory_tech_set = set(t.lower() for t in memory.tech_stack)
            tech_overlap = len(tech_set & memory_tech_set)

            # Score by feature overlap
            memory_feature_set = set(f.lower() for f in memory.features)
            feature_overlap = len(feature_set & memory_feature_set)

            score = tech_overlap * 3 + feature_overlap * 2

            if score > 0:
                memories.append((score, memory))

        # Sort by score descending
        memories.sort(key=lambda x: x[0], reverse=True)

        result = [m for _, m in memories[:limit]]

        logger.info(
            "build_memory.retrieved",
            tech_stack=tech_stack,
            total_memories=len(all_ids),
            relevant_count=len(result),
        )
        return result

    except Exception as e:
        logger.warning(
            "build_memory.retrieval_failed",
            error=str(e),
        )
        return []

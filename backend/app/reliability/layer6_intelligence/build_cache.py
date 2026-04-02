"""
Layer 6 — Build cache (Pinecone vector similarity).

Uses OpenAI embeddings + Pinecone to cache successful builds by semantic
similarity of the idea spec.  Target: 60% cache hit rate.

Only stores builds that passed ALL gates (quality guarantee).
"""

from __future__ import annotations

import hashlib
import json
import time

from pydantic import BaseModel, Field

import structlog

from app.config import settings

logger = structlog.get_logger(__name__)


# ── Pydantic models ──────────────────────────────────────────────────


class CacheResult(BaseModel):
    """Result from cache lookup."""

    hit: bool = True
    similarity_score: float = Field(ge=0.0, le=1.0)
    cached_files: dict[str, str] = Field(
        default_factory=dict,
        description="file_path → file_content from cached build",
    )
    build_id: str = ""
    tech_stack: list[str] = Field(default_factory=list)
    cached_at: str = ""
    time_saved_seconds: float = 0.0


# ── Embedding client ─────────────────────────────────────────────────

_SIMILARITY_THRESHOLD = 0.92
_EMBEDDING_MODEL = "text-embedding-3-small"
_EMBEDDING_DIMENSIONS = 1536


async def _get_embedding(text: str) -> list[float]:
    """Get embedding vector from OpenAI API.

    Uses text-embedding-3-small for cost efficiency.
    """
    try:
        import openai

        client = openai.AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        response = await client.embeddings.create(
            input=text,
            model=_EMBEDDING_MODEL,
        )
        return response.data[0].embedding
    except Exception as e:
        logger.error(
            "build_cache.embedding_failed",
            error=str(e),
        )
        raise


def _spec_to_text(idea_spec: dict[str, object]) -> str:
    """Convert an idea spec dict to a text string for embedding."""
    parts: list[str] = []

    title = idea_spec.get("title", "")
    if title:
        parts.append(f"Title: {title}")

    description = idea_spec.get("description", "")
    if description:
        parts.append(f"Description: {description}")

    features = idea_spec.get("features", [])
    if isinstance(features, list) and features:
        parts.append(f"Features: {', '.join(str(f) for f in features)}")

    framework = idea_spec.get("framework", "")
    if framework:
        parts.append(f"Framework: {framework}")

    return "\n".join(parts) if parts else json.dumps(idea_spec)


# ── Pinecone client ──────────────────────────────────────────────────


def _get_pinecone_index():
    """Get or create the Pinecone index for build cache.

    Returns the Pinecone index client.
    """
    try:
        from pinecone import Pinecone

        pc = Pinecone(api_key=settings.PINECONE_API_KEY)
        index_name = getattr(settings, "PINECONE_INDEX_NAME", "forge-build-cache")
        return pc.Index(index_name)
    except Exception as e:
        logger.error(
            "build_cache.pinecone_connection_failed",
            error=str(e),
        )
        raise


# ── Public API ───────────────────────────────────────────────────────


async def check_cache(
    idea_spec: dict[str, object],
    threshold: float = _SIMILARITY_THRESHOLD,
) -> CacheResult | None:
    """Check if a similar build exists in the cache.

    Args:
        idea_spec: The idea specification to search for.
        threshold: Minimum similarity score (default 0.92).

    Returns:
        CacheResult if a sufficiently similar build is found, None otherwise.
    """
    start_time = time.monotonic()

    try:
        # Embed the idea spec
        spec_text = _spec_to_text(idea_spec)
        embedding = await _get_embedding(spec_text)

        # Query Pinecone
        index = _get_pinecone_index()
        results = index.query(
            vector=embedding,
            top_k=1,
            include_metadata=True,
        )

        if not results.get("matches"):
            logger.info(
                "build_cache.miss",
                reason="no_matches",
            )
            return None

        best_match = results["matches"][0]
        similarity = best_match.get("score", 0.0)

        if similarity < threshold:
            logger.info(
                "build_cache.miss",
                reason="below_threshold",
                similarity=similarity,
                threshold=threshold,
            )
            return None

        # Cache hit!
        metadata = best_match.get("metadata", {})
        cached_files_json = metadata.get("generated_files", "{}")
        cached_files = json.loads(cached_files_json) if isinstance(
            cached_files_json, str
        ) else cached_files_json

        elapsed = time.monotonic() - start_time
        build_duration = float(metadata.get("build_duration", 0.0))

        logger.info(
            "build_cache.hit",
            similarity=similarity,
            build_id=metadata.get("build_id", ""),
            time_saved_seconds=max(0, build_duration - elapsed),
        )

        return CacheResult(
            hit=True,
            similarity_score=similarity,
            cached_files=cached_files if isinstance(cached_files, dict) else {},
            build_id=str(metadata.get("build_id", "")),
            tech_stack=metadata.get("tech_stack", []),
            cached_at=str(metadata.get("cached_at", "")),
            time_saved_seconds=max(0, build_duration - elapsed),
        )

    except Exception as e:
        logger.warning(
            "build_cache.check_failed",
            error=str(e),
        )
        return None


async def store_in_cache(
    idea_spec: dict[str, object],
    generated_files: dict[str, str],
    build_id: str = "",
    tech_stack: list[str] | None = None,
    build_duration: float = 0.0,
    *,
    gates_passed: bool = False,
) -> bool:
    """Store a successful build in the cache.

    ONLY stores builds that passed ALL gates (quality guarantee).
    The gates_passed flag MUST be explicitly set to True by the caller.
    This prevents cache poisoning from failed or partial builds.

    Args:
        idea_spec: The idea specification used for the build.
        generated_files: Dict of file_path → file_content.
        build_id: Build identifier.
        tech_stack: List of technologies used.
        build_duration: How long the build took in seconds.
        gates_passed: Must be True — enforced at API level.

    Returns:
        True if stored successfully, False otherwise.
    """
    if not gates_passed:
        logger.warning(
            "build_cache.store_rejected",
            build_id=build_id,
            reason="gates_not_passed",
        )
        return False
    try:
        # Embed the idea spec
        spec_text = _spec_to_text(idea_spec)
        embedding = await _get_embedding(spec_text)

        # Generate a unique vector ID
        spec_hash = hashlib.sha256(spec_text.encode()).hexdigest()[:16]
        vector_id = f"build-{spec_hash}"

        # Prepare metadata
        metadata = {
            "build_id": build_id,
            "idea_spec": json.dumps(idea_spec),
            "generated_files": json.dumps(generated_files),
            "tech_stack": tech_stack or [],
            "build_duration": build_duration,
            "cached_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "file_count": len(generated_files),
        }

        # Upsert to Pinecone
        index = _get_pinecone_index()
        index.upsert(
            vectors=[
                {
                    "id": vector_id,
                    "values": embedding,
                    "metadata": metadata,
                }
            ]
        )

        logger.info(
            "build_cache.stored",
            vector_id=vector_id,
            build_id=build_id,
            file_count=len(generated_files),
        )
        return True

    except Exception as e:
        logger.error(
            "build_cache.store_failed",
            error=str(e),
        )
        return False

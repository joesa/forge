"""
Layer 10 — Context window manager.

Manages context window limits for all build agents.  When context
exceeds 60% of a model's token limit, splits into overlapping chunks,
generates independently for each chunk, and merges results with seam
validation.

Token estimation: 4 characters ≈ 1 token.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Callable, Coroutine

import structlog

logger = structlog.get_logger(__name__)

# Characters per token (rough estimation)
CHARS_PER_TOKEN = 4

# Overlap between chunks (in tokens)
CHUNK_OVERLAP_TOKENS = 200

# Threshold: if context exceeds this fraction of the model limit, chunk
CHUNKING_THRESHOLD = 0.60


# ── Model limits ─────────────────────────────────────────────────────

MODEL_LIMITS: dict[str, int] = {
    "claude-opus-4-6": 200_000,
    "claude-sonnet-4-6": 200_000,
    "gpt-4o": 128_000,
    "gemini-3-pro": 1_000_000,
}

# Default limit for unknown models
DEFAULT_MODEL_LIMIT = 128_000


# ── Types ────────────────────────────────────────────────────────────


@dataclass
class ChunkInfo:
    """Metadata about a processed chunk."""

    chunk_index: int
    start_token: int
    end_token: int
    token_count: int


@dataclass
class MergeResult:
    """Result from the context window manager."""

    output: dict[str, Any] = field(default_factory=dict)
    chunks_used: int = 1
    was_chunked: bool = False
    total_tokens_estimated: int = 0
    model_limit: int = 0
    seam_issues: list[str] = field(default_factory=list)


# ── Token estimation ────────────────────────────────────────────────


def estimate_tokens(text: str) -> int:
    """Estimate token count from character count.

    Rule: 4 characters ≈ 1 token.
    """
    return max(1, len(text) // CHARS_PER_TOKEN)


def estimate_context_tokens(context: dict[str, Any]) -> int:
    """Estimate total tokens for a context dictionary."""
    serialized = json.dumps(context, default=str)
    return estimate_tokens(serialized)


# ── Chunking ─────────────────────────────────────────────────────────


def _split_context(
    context: dict[str, Any],
    max_tokens_per_chunk: int,
    overlap_tokens: int = CHUNK_OVERLAP_TOKENS,
) -> list[dict[str, Any]]:
    """Split a context dict into overlapping chunks.

    The context is serialized, split at token boundaries, and each
    chunk is reconstructed as a partial context dict.
    """
    serialized = json.dumps(context, default=str)
    total_chars = len(serialized)
    chunk_chars = max_tokens_per_chunk * CHARS_PER_TOKEN
    overlap_chars = overlap_tokens * CHARS_PER_TOKEN

    if total_chars <= chunk_chars:
        return [context]

    chunks: list[dict[str, Any]] = []
    start = 0

    while start < total_chars:
        end = min(start + chunk_chars, total_chars)

        # Extract the chunk text
        chunk_text = serialized[start:end]

        # Wrap in a context dict
        chunk_dict: dict[str, Any] = {
            "_chunk_index": len(chunks),
            "_total_chunks": -1,  # Will be updated after splitting
            "_chunk_start_char": start,
            "_chunk_end_char": end,
        }

        # Try to parse the chunk as JSON (it probably won't be valid)
        # Instead, inject the raw chunk as a string key
        try:
            parsed = json.loads(chunk_text)
            if isinstance(parsed, dict):
                chunk_dict.update(parsed)
            else:
                chunk_dict["_partial_context"] = chunk_text
        except json.JSONDecodeError:
            chunk_dict["_partial_context"] = chunk_text

        chunks.append(chunk_dict)

        # Advance with overlap
        step = chunk_chars - overlap_chars
        if step <= 0:
            step = chunk_chars  # Avoid infinite loop
        start += step

    # Update total chunks count
    for chunk in chunks:
        chunk["_total_chunks"] = len(chunks)

    return chunks


# ── Seam checker ─────────────────────────────────────────────────────


def check_seam(
    chunk_a_output: dict[str, Any],
    chunk_b_output: dict[str, Any],
) -> list[str]:
    """Validate the seam between two adjacent chunk outputs.

    Checks for:
    - Duplicate keys (files generated in both chunks)
    - Missing cross-references
    - Inconsistent naming

    Returns a list of issues found.
    """
    issues: list[str] = []

    # Check for generated file overlaps
    files_a = set(chunk_a_output.get("files", {}).keys())
    files_b = set(chunk_b_output.get("files", {}).keys())
    overlap = files_a & files_b

    if overlap:
        issues.append(
            f"Duplicate files generated in adjacent chunks: {overlap}"
        )

    # Check for import consistency
    imports_a = set(chunk_a_output.get("imports", []))
    exports_b = set(chunk_b_output.get("exports", []))
    missing_exports = imports_a - exports_b
    if missing_exports and exports_b:
        issues.append(
            f"Chunk A imports not exported by chunk B: {missing_exports}"
        )

    return issues


def _merge_chunk_outputs(
    outputs: list[dict[str, Any]],
) -> tuple[dict[str, Any], list[str]]:
    """Merge multiple chunk outputs into a single result.

    Returns (merged_dict, seam_issues).
    """
    if not outputs:
        return {}, []

    if len(outputs) == 1:
        return outputs[0], []

    merged: dict[str, Any] = {}
    all_issues: list[str] = []

    for output in outputs:
        # Merge file dictionaries
        if "files" in output:
            if "files" not in merged:
                merged["files"] = {}
            merged["files"].update(output["files"])

        # Merge other keys (last-writer-wins for scalars)
        for key, value in output.items():
            if key == "files":
                continue
            if key.startswith("_chunk"):
                continue
            if isinstance(value, dict) and key in merged and isinstance(merged[key], dict):
                merged[key].update(value)
            elif isinstance(value, list) and key in merged and isinstance(merged[key], list):
                merged[key].extend(value)
            else:
                merged[key] = value

    # Run seam checks between adjacent chunks
    for i in range(len(outputs) - 1):
        issues = check_seam(outputs[i], outputs[i + 1])
        all_issues.extend(issues)

    return merged, all_issues


# ── Context Window Manager class ────────────────────────────────────


class ContextWindowManager:
    """Manages context window limits for build agents.

    Attributes
    ----------
    LIMITS : dict[str, int]
        Model name → max token count mapping.
    """

    LIMITS = MODEL_LIMITS

    def __init__(
        self,
        default_model: str = "claude-sonnet-4-6",
    ) -> None:
        self.default_model = default_model

    def get_model_limit(self, model: str) -> int:
        """Get the token limit for a model."""
        return self.LIMITS.get(model, DEFAULT_MODEL_LIMIT)

    def needs_chunking(self, context: dict[str, Any], model: str) -> bool:
        """Check if context exceeds the chunking threshold."""
        token_est = estimate_context_tokens(context)
        limit = self.get_model_limit(model)
        return token_est > (limit * CHUNKING_THRESHOLD)

    async def managed_generate(
        self,
        agent_fn: Callable[..., Coroutine[Any, Any, dict[str, Any]]],
        context: dict[str, Any],
        model: str,
    ) -> MergeResult:
        """Generate output with automatic context window management.

        If context exceeds 60% of the model's limit, splits into
        overlapping chunks, generates independently for each, and merges.

        Parameters
        ----------
        agent_fn : Callable
            Async function that takes a context dict and returns output dict.
        context : dict
            The full context to process.
        model : str
            Model identifier (used to look up token limits).

        Returns
        -------
        MergeResult
            Merged output with metadata about chunking.
        """
        result = MergeResult()
        limit = self.get_model_limit(model)
        token_est = estimate_context_tokens(context)
        result.total_tokens_estimated = token_est
        result.model_limit = limit

        threshold = int(limit * CHUNKING_THRESHOLD)

        if token_est <= threshold:
            # Context fits — generate directly
            try:
                output = await agent_fn(context)
                result.output = output
                result.was_chunked = False
                result.chunks_used = 1

                logger.info(
                    "context_window.direct_generate",
                    model=model,
                    tokens=token_est,
                    limit=limit,
                )
            except Exception as exc:
                logger.error(
                    "context_window.generate_failed",
                    error=str(exc),
                )
                raise

            return result

        # Context too large — chunk it
        logger.info(
            "context_window.chunking_required",
            model=model,
            tokens=token_est,
            limit=limit,
            threshold=threshold,
        )

        max_tokens_per_chunk = threshold
        chunks = _split_context(
            context,
            max_tokens_per_chunk,
            CHUNK_OVERLAP_TOKENS,
        )

        result.was_chunked = True
        result.chunks_used = len(chunks)

        # Generate for each chunk
        chunk_outputs: list[dict[str, Any]] = []
        for i, chunk in enumerate(chunks):
            try:
                output = await agent_fn(chunk)
                chunk_outputs.append(output)
                logger.info(
                    "context_window.chunk_processed",
                    chunk=i + 1,
                    total=len(chunks),
                )
            except Exception as exc:
                logger.error(
                    "context_window.chunk_failed",
                    chunk=i + 1,
                    error=str(exc),
                )
                raise

        # Merge results
        merged, seam_issues = _merge_chunk_outputs(chunk_outputs)
        result.output = merged
        result.seam_issues = seam_issues

        if seam_issues:
            logger.warning(
                "context_window.seam_issues",
                count=len(seam_issues),
                issues=seam_issues[:5],
            )

        logger.info(
            "context_window.merge_complete",
            chunks=len(chunks),
            seam_issues=len(seam_issues),
        )

        return result

"""
Context Window Manager — wraps every LLM call in the build pipeline.

If the prompt exceeds 60% of the model's context limit, the manager
splits the prompt into overlapping chunks (200-token overlap), calls
the LLM once per chunk, and re-merges the partial outputs.

Token estimation: ~4 characters per token (conservative estimate).
"""

from __future__ import annotations

import json
import time
from typing import Any

import structlog

from app.agents.ai_router import AIRouter

logger = structlog.get_logger(__name__)

# Token estimation constant
CHARS_PER_TOKEN = 4

# Default context limit (128k tokens for Claude/GPT-4 class models)
DEFAULT_CONTEXT_LIMIT = 128_000

# Threshold: split if prompt exceeds this fraction of context limit
SPLIT_THRESHOLD = 0.60

# Overlap between chunks when splitting (in tokens)
CHUNK_OVERLAP_TOKENS = 200


class ContextWindowManager:
    """Manages LLM context window limits for build agents.

    Wraps every LLM call:
      - Estimates token count from prompt length
      - If > 60% of context limit: splits into chunks with 200-token overlap
      - Calls LLM per chunk and merges results

    All build agents use temperature=0, fixed seed (Architecture rule #4).
    """

    def __init__(
        self,
        ai_router: AIRouter,
        context_limit: int = DEFAULT_CONTEXT_LIMIT,
    ) -> None:
        self.ai_router = ai_router
        self.context_limit = context_limit
        self.split_threshold_tokens = int(context_limit * SPLIT_THRESHOLD)

    def _estimate_tokens(self, text: str) -> int:
        """Estimate token count from character length."""
        return len(text) // CHARS_PER_TOKEN

    def _split_prompt(self, prompt: str) -> list[str]:
        """Split a prompt into overlapping chunks.

        Each chunk is sized to stay under the split threshold.
        Adjacent chunks share a 200-token (800-char) overlap region
        so context is not lost at boundaries.
        """
        chunk_size_chars = self.split_threshold_tokens * CHARS_PER_TOKEN
        # Clamp overlap to at most half the chunk size to avoid zero/negative stride
        overlap_chars = min(
            CHUNK_OVERLAP_TOKENS * CHARS_PER_TOKEN,
            chunk_size_chars // 2,
        )
        stride = max(chunk_size_chars - overlap_chars, 1)

        chunks: list[str] = []
        start = 0
        text_len = len(prompt)

        while start < text_len:
            end = min(start + chunk_size_chars, text_len)
            chunks.append(prompt[start:end])
            start += stride
            if end >= text_len:
                break

        logger.info(
            "context_window_manager.split",
            total_chars=text_len,
            estimated_tokens=self._estimate_tokens(prompt),
            chunks=len(chunks),
            chunk_size_chars=chunk_size_chars,
            overlap_chars=overlap_chars,
        )
        return chunks

    def _merge_file_results(self, results: list[dict[str, str]]) -> dict[str, str]:
        """Merge file dictionaries from multiple chunk responses.

        Later chunks overwrite earlier ones for the same file path.
        This is intentional — later chunks have more complete context.
        """
        merged: dict[str, str] = {}
        for result in results:
            merged.update(result)
        return merged

    async def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        agent_name: str,
    ) -> dict[str, str]:
        """Generate code via LLM with automatic context window management.

        Parameters
        ----------
        system_prompt : str
            System prompt for the LLM.
        user_prompt : str
            User prompt containing the generation task.
        agent_name : str
            Name of the calling agent (for logging).

        Returns
        -------
        dict[str, str]
            Mapping of file_path → file_content.
        """
        start = time.monotonic()
        full_prompt = system_prompt + "\n\n" + user_prompt
        estimated_tokens = self._estimate_tokens(full_prompt)

        logger.info(
            "context_window_manager.generate",
            agent=agent_name,
            estimated_tokens=estimated_tokens,
            threshold=self.split_threshold_tokens,
            needs_split=estimated_tokens > self.split_threshold_tokens,
        )

        if estimated_tokens <= self.split_threshold_tokens:
            # Single call — fits within context window
            raw = await self.ai_router.complete(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=0.0,  # Architecture rule #4
                response_format="json",
            )
            result = self._parse_response(raw, agent_name)
        else:
            # Multi-chunk generation
            chunks = self._split_prompt(user_prompt)
            chunk_results: list[dict[str, str]] = []

            for i, chunk in enumerate(chunks):
                chunk_system = (
                    f"{system_prompt}\n\n"
                    f"[Context Window Manager: Chunk {i + 1}/{len(chunks)}]\n"
                    f"This is part of a split generation. Produce files only "
                    f"for the content described in this chunk."
                )
                raw = await self.ai_router.complete(
                    system_prompt=chunk_system,
                    user_prompt=chunk,
                    temperature=0.0,  # Architecture rule #4
                    response_format="json",
                )
                chunk_result = self._parse_response(raw, f"{agent_name}_chunk_{i}")
                chunk_results.append(chunk_result)

            result = self._merge_file_results(chunk_results)

        elapsed = time.monotonic() - start
        logger.info(
            "context_window_manager.complete",
            agent=agent_name,
            files_generated=len(result),
            elapsed_s=round(elapsed, 3),
        )
        return result

    def _parse_response(self, raw: str, agent_name: str) -> dict[str, str]:
        """Parse LLM response as a JSON dict of file_path → file_content.

        Falls back to empty dict on parse failure.
        """
        try:
            data: Any = json.loads(raw)
            if isinstance(data, dict):
                # Validate all values are strings
                return {
                    str(k): str(v) for k, v in data.items()
                    if isinstance(k, str)
                }
            logger.warning(
                "context_window_manager.invalid_format",
                agent=agent_name,
                type=type(data).__name__,
            )
            return {}
        except (json.JSONDecodeError, TypeError) as exc:
            logger.warning(
                "context_window_manager.parse_error",
                agent=agent_name,
                error=str(exc),
            )
            return {}

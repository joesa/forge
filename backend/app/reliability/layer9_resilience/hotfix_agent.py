"""
Layer 9 — Hotfix agent.

Repairs targeted gate failures WITHOUT a full rebuild.  The agent
identifies the single file responsible, extracts the failing function or
component, generates a minimal fix, and re-runs the failed gate.

Maximum 3 attempts per gate failure.  Temperature is forced to 0 (same
deterministic mode as all build agents — AGENTS.md rule #4).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Callable, Coroutine

import structlog

logger = structlog.get_logger(__name__)

# Maximum number of repair attempts per gate failure
MAX_ATTEMPTS = 3

# Temperature forced for hotfix generation (AGENTS.md rule #4)
HOTFIX_TEMPERATURE = 0.0


# ── Types ────────────────────────────────────────────────────────────


@dataclass
class HotfixContext:
    """Error context provided to the hotfix agent."""

    failed_gate: str  # e.g. "G7", "G8", "G10"
    error_message: str
    failing_file: str
    error_line: int | None = None


@dataclass
class HotfixChange:
    """A single change applied by the hotfix agent."""

    file_path: str
    original_snippet: str
    fixed_snippet: str
    explanation: str = ""


@dataclass
class HotfixResult:
    """Outcome of a hotfix attempt."""

    success: bool = False
    changes: list[HotfixChange] = field(default_factory=list)
    attempts: int = 0
    gate_re_ran: str = ""
    error: str | None = None


# ── Internal helpers ─────────────────────────────────────────────────


def _extract_error_region(
    file_content: str,
    error_line: int | None,
    *,
    context_lines: int = 15,
) -> str:
    """Extract source region around the error line.

    Returns the full file if error_line is None or the file is short.
    """
    lines = file_content.split("\n")

    if error_line is None or len(lines) <= context_lines * 2:
        return file_content

    # Clamp to valid range
    start = max(0, error_line - 1 - context_lines)
    end = min(len(lines), error_line + context_lines)
    return "\n".join(lines[start:end])


def _build_hotfix_prompt(
    error_context: HotfixContext,
    file_content: str,
    attempt: int,
) -> tuple[str, str]:
    """Build system + user prompts for the hotfix LLM call."""
    error_region = _extract_error_region(
        file_content, error_context.error_line
    )

    system_prompt = (
        "You are FORGE Hotfix Agent. You repair a single code error with "
        "minimal, targeted changes. Rules:\n"
        "1. Only change the specific function/component causing the failure.\n"
        "2. Do NOT rewrite the entire file — return only the fixed section.\n"
        "3. Preserve all existing imports, types, and exports.\n"
        "4. Return valid JSON with keys: fixed_code, explanation.\n"
        "5. fixed_code must be a drop-in replacement for the broken section.\n"
    )

    user_prompt = (
        f"Gate {error_context.failed_gate} failed.\n"
        f"Error: {error_context.error_message}\n"
        f"File: {error_context.failing_file}\n"
        f"Error line: {error_context.error_line}\n"
        f"Attempt: {attempt}/{MAX_ATTEMPTS}\n\n"
        f"Source region:\n```\n{error_region}\n```\n\n"
        "Return JSON: {\"fixed_code\": \"...\", \"explanation\": \"...\"}"
    )

    return system_prompt, user_prompt


def _apply_fix_to_content(
    file_content: str,
    error_region: str,
    fixed_code: str,
) -> str:
    """Replace the error region in the file with the fixed code.

    Falls back to full replacement if the exact region is not found
    (LLM may have slightly modified the boundaries).
    """
    if error_region in file_content:
        return file_content.replace(error_region, fixed_code, 1)
    # Fallback: replace the entire file content with the fix
    return fixed_code


def _parse_hotfix_response(raw_response: str) -> dict[str, str]:
    """Parse the LLM response into fixed_code + explanation.

    Handles both clean JSON and markdown-wrapped JSON.
    """
    # Strip markdown code fences if present
    cleaned = raw_response.strip()
    if cleaned.startswith("```"):
        # Remove opening fence (```json or ```)
        cleaned = re.sub(r"^```(?:json)?\s*\n?", "", cleaned)
        # Remove closing fence
        cleaned = re.sub(r"\n?```\s*$", "", cleaned)

    try:
        parsed = json.loads(cleaned)
        return {
            "fixed_code": parsed.get("fixed_code", ""),
            "explanation": parsed.get("explanation", ""),
        }
    except json.JSONDecodeError:
        # If JSON parsing fails, treat the whole response as the fix
        return {
            "fixed_code": cleaned,
            "explanation": "LLM response was not valid JSON; used raw text.",
        }


# ── Gate re-runner type ──────────────────────────────────────────────

# A gate validator is an async function that takes the generated files
# and returns a dict with at least a "passed" key.
GateValidator = Callable[
    [dict[str, str]],
    Coroutine[Any, Any, dict[str, Any]],
]


# ── Public API ───────────────────────────────────────────────────────


async def apply_hotfix(
    error_context: HotfixContext,
    generated_files: dict[str, str],
    ai_router: Any,
    *,
    gate_validator: GateValidator | None = None,
) -> HotfixResult:
    """Attempt to repair a gate failure with minimal targeted changes.

    Parameters
    ----------
    error_context : HotfixContext
        Details about the gate failure.
    generated_files : dict[str, str]
        Current mapping of file_path → file_content.
    ai_router : AIRouterProtocol
        LLM router (calls are forced to temperature=0).
    gate_validator : GateValidator | None
        Optional async function that re-runs the failed gate.
        Accepts generated_files, returns dict with ``passed`` bool.

    Returns
    -------
    HotfixResult
        Result with success status and list of changes made.
    """
    result = HotfixResult(gate_re_ran=error_context.failed_gate)

    failing_file = error_context.failing_file
    if failing_file not in generated_files:
        result.error = f"Failing file not found: {failing_file}"
        logger.error("hotfix.file_not_found", file=failing_file)
        return result

    original_content = generated_files[failing_file]

    for attempt in range(1, MAX_ATTEMPTS + 1):
        result.attempts = attempt

        try:
            # Build prompts
            system_prompt, user_prompt = _build_hotfix_prompt(
                error_context,
                generated_files[failing_file],
                attempt,
            )

            # Call LLM at temperature=0 (deterministic)
            raw_response = await ai_router.complete(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=HOTFIX_TEMPERATURE,
                response_format="json",
            )

            # Parse response
            parsed = _parse_hotfix_response(raw_response)
            fixed_code = parsed["fixed_code"]
            explanation = parsed["explanation"]

            if not fixed_code:
                logger.warning(
                    "hotfix.empty_fix",
                    attempt=attempt,
                    gate=error_context.failed_gate,
                )
                continue

            # Extract the region we're replacing
            error_region = _extract_error_region(
                generated_files[failing_file],
                error_context.error_line,
            )

            # Apply the fix
            patched_content = _apply_fix_to_content(
                generated_files[failing_file],
                error_region,
                fixed_code,
            )

            # Record the change
            change = HotfixChange(
                file_path=failing_file,
                original_snippet=error_region[:500],
                fixed_snippet=fixed_code[:500],
                explanation=explanation,
            )
            result.changes.append(change)

            # Update the generated files with the fix
            generated_files[failing_file] = patched_content

            # Re-run the gate if a validator is provided
            if gate_validator is not None:
                gate_result = await gate_validator(generated_files)
                if gate_result.get("passed", False):
                    result.success = True
                    logger.info(
                        "hotfix.success",
                        gate=error_context.failed_gate,
                        attempt=attempt,
                        file=failing_file,
                    )
                    return result
                else:
                    logger.warning(
                        "hotfix.gate_still_failing",
                        gate=error_context.failed_gate,
                        attempt=attempt,
                    )
            else:
                # No validator — assume success if fix was generated
                result.success = True
                logger.info(
                    "hotfix.applied_no_validate",
                    gate=error_context.failed_gate,
                    attempt=attempt,
                    file=failing_file,
                )
                return result

        except Exception as exc:
            logger.error(
                "hotfix.attempt_failed",
                attempt=attempt,
                error=str(exc),
                gate=error_context.failed_gate,
            )
            result.error = str(exc)

    # All attempts exhausted — restore original content
    generated_files[failing_file] = original_content
    result.success = False
    result.error = (
        f"Hotfix failed after {MAX_ATTEMPTS} attempts for "
        f"gate {error_context.failed_gate}"
    )
    logger.error(
        "hotfix.exhausted",
        gate=error_context.failed_gate,
        file=failing_file,
        attempts=MAX_ATTEMPTS,
    )
    return result

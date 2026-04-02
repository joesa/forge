"""
Layer 4 — Seam checker.

Detects truncated file output from context-window chunking:
  - Unclosed braces / brackets / parentheses
  - Incomplete function definitions
  - Missing closing JSX tags
  - Truncation markers (// ..., /* ..., etc.)
"""

from __future__ import annotations

import re

from pydantic import BaseModel, Field

import structlog

logger = structlog.get_logger(__name__)


class SeamReport(BaseModel):
    """Result of checking a single file for seam/truncation errors."""

    file_path: str
    valid: bool
    issues: list[str] = Field(default_factory=list)


# ── Truncation markers ───────────────────────────────────────────────

_TRUNCATION_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"//\s*\.\.\.\s*$", re.MULTILINE),
    re.compile(r"/\*\s*\.\.\.\s*\*/\s*$", re.MULTILINE),
    re.compile(r"//\s*rest of (?:code|file|implementation)", re.IGNORECASE),
    re.compile(r"//\s*TODO:?\s*(?:implement|add|complete)", re.IGNORECASE),
    re.compile(r"//\s*\.\.\.\s*(?:more|etc|and so on)", re.IGNORECASE),
    re.compile(r"//\s*truncated", re.IGNORECASE),
    re.compile(r"//\s*continued", re.IGNORECASE),
]


def check_seam(file_path: str, content: str) -> SeamReport:
    """Check a file for seam/truncation errors.

    Args:
        file_path: The file path (for reporting).
        content: The file content to check.

    Returns:
        SeamReport with validity status and list of issues.
    """
    issues: list[str] = []

    if not content or not content.strip():
        return SeamReport(
            file_path=file_path,
            valid=False,
            issues=["file is empty"],
        )

    # 1. Check brace balance
    open_braces = content.count("{")
    close_braces = content.count("}")
    if open_braces != close_braces:
        diff = open_braces - close_braces
        if diff > 0:
            issues.append(
                f"unclosed braces: {diff} opening '{{' without matching '}}'"
            )
        else:
            issues.append(
                f"extra closing braces: {-diff} '}}' without matching '{{'"
            )

    # 2. Check bracket balance
    open_brackets = content.count("[")
    close_brackets = content.count("]")
    if open_brackets != close_brackets:
        diff = open_brackets - close_brackets
        if diff > 0:
            issues.append(
                f"unclosed brackets: {diff} opening '[' without matching ']'"
            )
        else:
            issues.append(
                f"extra closing brackets: {-diff} ']' without matching '['"
            )

    # 3. Check parenthesis balance
    open_parens = content.count("(")
    close_parens = content.count(")")
    if open_parens != close_parens:
        diff = open_parens - close_parens
        if diff > 0:
            issues.append(
                f"unclosed parentheses: {diff} opening '(' without matching ')'"
            )
        else:
            issues.append(
                f"extra closing parentheses: {-diff} ')' without matching '('"
            )

    # 4. Check for truncation markers
    for pattern in _TRUNCATION_PATTERNS:
        matches = pattern.findall(content)
        if matches:
            issues.append(
                f"truncation marker detected: '{matches[0].strip()}'"
            )

    # 5. Check for incomplete JSX (unmatched opening tags)
    if file_path.endswith((".tsx", ".jsx")):
        _check_jsx_completeness(content, issues)

    # 6. Check file ends abruptly (no newline, ends mid-statement)
    stripped = content.rstrip()
    if stripped:
        last_char = stripped[-1]
        # Files should end with }, ), ;, `, or a closing tag
        valid_endings = ("}", ")", ";", "`", ">", '"', "'", "/", "]")
        if last_char not in valid_endings and not stripped.endswith("*/"):
            # Check if the last line looks incomplete
            last_line = stripped.split("\n")[-1].strip()
            # Allow comments and blank lines
            if (
                not last_line.startswith("//")
                and not last_line.startswith("*")
                and last_line != ""
            ):
                issues.append(
                    f"file ends abruptly with '{last_char}' — "
                    f"last line: '{last_line[:60]}'"
                )

    valid = len(issues) == 0

    if not valid:
        logger.warning(
            "seam_checker.issues_found",
            file_path=file_path,
            issue_count=len(issues),
        )

    return SeamReport(
        file_path=file_path,
        valid=valid,
        issues=issues,
    )


def _check_jsx_completeness(content: str, issues: list[str]) -> None:
    """Check for unmatched JSX opening tags."""
    # Simple check: find component-style tags (capitalized, not self-closing)
    opening_tags = re.findall(r"<([A-Z]\w+)(?:\s[^>]*)?>", content)
    closing_tags = re.findall(r"</([A-Z]\w+)>", content)
    self_closing = re.findall(r"<([A-Z]\w+)(?:\s[^>]*)?\s*/>", content)

    # Remove self-closing from opening count
    open_set: dict[str, int] = {}
    for tag in opening_tags:
        open_set[tag] = open_set.get(tag, 0) + 1
    for tag in self_closing:
        open_set[tag] = open_set.get(tag, 0) - 1

    close_set: dict[str, int] = {}
    for tag in closing_tags:
        close_set[tag] = close_set.get(tag, 0) + 1

    for tag, count in open_set.items():
        close_count = close_set.get(tag, 0)
        if count > close_count:
            issues.append(
                f"unclosed JSX tag: <{tag}> opened {count} times "
                f"but closed {close_count} times"
            )

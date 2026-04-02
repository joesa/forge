"""
Layer 3 — AST analyser (Python regex-based).

Analyses TypeScript/TSX files for common patterns that cause runtime errors.
Called inline by each build agent on its own output — not as a post-build step.

Detection rules:
  1. Null reference patterns (obj.prop without ?. or null check)
  2. Unhandled promise rejections (async calls without try/catch)
  3. Missing error boundaries in React component trees
  4. Zustand store mutations (must use immer set() pattern)
"""

from __future__ import annotations

import re

from pydantic import BaseModel, Field

import structlog

logger = structlog.get_logger(__name__)


# ── Pydantic models ──────────────────────────────────────────────────


class ASTIssue(BaseModel):
    """A single issue found during static analysis."""

    file: str
    line: int = Field(ge=1)
    rule: str = Field(
        description="null_ref | unhandled_promise | missing_error_boundary | "
        "zustand_mutation | unsafe_any | missing_return_type"
    )
    severity: str = Field(description="warning | error")
    message: str
    suggestion: str = ""


class ASTReport(BaseModel):
    """Full static analysis report for a single file."""

    file_path: str
    issues: list[ASTIssue] = Field(default_factory=list)
    severity: str = Field(
        default="warning",
        description="Worst severity: 'warning' if no errors, 'error' if any",
    )
    lines_analysed: int = 0


# ── Detection patterns ───────────────────────────────────────────────

# Pattern: access chain without optional chaining where variable could be null
# Matches: data.user.name but NOT data?.user?.name
_NULL_REF_CHAIN_RE = re.compile(
    r"\b(\w+)\.(\w+)\.(\w+)\b"
)
# Matches optional chaining to exclude from null ref warnings
_OPTIONAL_CHAIN_RE = re.compile(
    r"\b\w+\?\.\w+"
)

# Patterns indicating a variable might be nullable
_NULLABLE_DECLARATIONS = re.compile(
    r"(?:const|let|var)\s+(\w+)\s*(?::\s*\w+(?:\s*\|\s*(?:null|undefined)))"
)

# Pattern: async function call without surrounding try/catch
_ASYNC_CALL_RE = re.compile(
    r"\bawait\s+\w+",
)
_TRY_BLOCK_RE = re.compile(r"\btry\s*\{")
_CATCH_BLOCK_RE = re.compile(r"\}\s*catch\s*\(")

# Pattern: React component file without ErrorBoundary wrapper
_REACT_COMPONENT_RE = re.compile(
    r"export\s+(?:default\s+)?function\s+(\w+)\s*\(",
)
_ERROR_BOUNDARY_RE = re.compile(
    r"ErrorBoundary",
    re.IGNORECASE,
)

# Pattern: Zustand store with direct state mutation
_ZUSTAND_CREATE_RE = re.compile(
    r"create\s*(?:<[^>]*>)?\s*\(",
)
_DIRECT_MUTATION_RE = re.compile(
    r"state\.(\w+)\s*(?:=(?!=)|\.push\(|\.splice\(|\.pop\(|\.shift\(|\.unshift\()",
)
_IMMER_PATTERN_RE = re.compile(
    r"(?:immer|produce|set\s*\()",
)

# Pattern: useEffect/useState in render body causing infinite loops
_SET_STATE_IN_RENDER_RE = re.compile(
    r"^\s*set\w+\s*\(",
    re.MULTILINE,
)

# TS extensions we care about
_TS_EXTENSIONS = (".ts", ".tsx", ".js", ".jsx")


# ── Analysis functions ───────────────────────────────────────────────


def _is_page_component(file_path: str) -> bool:
    """Check if a file is likely a page-level React component."""
    lower = file_path.lower()
    return (
        "/pages/" in lower
        or "/app/" in lower
        or lower.endswith("page.tsx")
        or lower.endswith("page.jsx")
    )


def _check_null_references(
    file_path: str,
    lines: list[str],
    nullable_vars: set[str],
) -> list[ASTIssue]:
    """Detect property access on potentially null variables."""
    issues: list[ASTIssue] = []

    for i, line in enumerate(lines, start=1):
        stripped = line.strip()
        # Skip comments
        if stripped.startswith("//") or stripped.startswith("*"):
            continue

        # Find chained property access
        for match in _NULL_REF_CHAIN_RE.finditer(line):
            root_var = match.group(1)

            # Skip if using optional chaining anywhere on this line
            if _OPTIONAL_CHAIN_RE.search(line):
                continue

            # Skip common safe patterns
            if root_var in (
                "console", "Math", "Object", "Array", "JSON",
                "window", "document", "process", "React",
                "import", "export", "const", "let", "var",
                "this", "super", "Promise", "Error", "Map", "Set",
            ):
                continue

            # Only warn if variable was declared nullable or comes from
            # common nullable sources (params, API responses, state)
            if root_var in nullable_vars:
                issues.append(ASTIssue(
                    file=file_path,
                    line=i,
                    rule="null_ref",
                    severity="warning",
                    message=(
                        f"Property chain '{match.group(0)}' on potentially "
                        f"null variable '{root_var}' without optional chaining"
                    ),
                    suggestion=(
                        f"Use optional chaining: "
                        f"{root_var}?.{match.group(2)}?.{match.group(3)}"
                    ),
                ))

    return issues


def _check_unhandled_promises(
    file_path: str,
    content: str,
    lines: list[str],
) -> list[ASTIssue]:
    """Detect await calls not wrapped in try/catch."""
    issues: list[ASTIssue] = []

    # Find all await expressions and check if they're inside try blocks
    # Simple heuristic: track brace depth relative to try blocks
    in_try_block = False
    try_brace_depth = 0
    brace_depth = 0

    for i, line in enumerate(lines, start=1):
        stripped = line.strip()
        if stripped.startswith("//") or stripped.startswith("*"):
            continue

        # Track brace depth
        brace_depth += line.count("{") - line.count("}")

        # Detect try block entry
        if _TRY_BLOCK_RE.search(line):
            in_try_block = True
            try_brace_depth = brace_depth

        # Detect catch (end of try block)
        if _CATCH_BLOCK_RE.search(line):
            in_try_block = False

        # If brace depth falls below try block depth, we left the try
        if in_try_block and brace_depth < try_brace_depth:
            in_try_block = False

        # Check for await without try/catch
        if _ASYNC_CALL_RE.search(line) and not in_try_block:
            # Skip if line has .catch() chained
            if ".catch(" in line:
                continue
            # Skip if it's in a try...catch style error handling
            issues.append(ASTIssue(
                file=file_path,
                line=i,
                rule="unhandled_promise",
                severity="warning",
                message=(
                    f"Async call without try/catch or .catch() handler"
                ),
                suggestion="Wrap in try/catch or chain .catch() for error handling",
            ))

    return issues


def _check_missing_error_boundaries(
    file_path: str,
    content: str,
) -> list[ASTIssue]:
    """Detect page components without ErrorBoundary wrappers."""
    issues: list[ASTIssue] = []

    if not _is_page_component(file_path):
        return issues

    # Check if file has React component exports
    component_match = _REACT_COMPONENT_RE.search(content)
    if not component_match:
        return issues

    # Check if ErrorBoundary is referenced
    if _ERROR_BOUNDARY_RE.search(content):
        return issues

    component_name = component_match.group(1)
    issues.append(ASTIssue(
        file=file_path,
        line=component_match.start()
        // max(1, content[:component_match.start()].count("\n")) + 1,
        rule="missing_error_boundary",
        severity="warning",
        message=(
            f"Page component '{component_name}' has no ErrorBoundary wrapper"
        ),
        suggestion=(
            "Wrap component tree in <ErrorBoundary> from "
            "'components/ui/ErrorBoundary'"
        ),
    ))

    return issues


def _check_zustand_mutations(
    file_path: str,
    content: str,
    lines: list[str],
) -> list[ASTIssue]:
    """Detect direct state mutations in Zustand stores."""
    issues: list[ASTIssue] = []

    # Only check files that look like Zustand stores
    if not _ZUSTAND_CREATE_RE.search(content):
        return issues

    # Check if immer is being used (which makes mutations safe)
    if _IMMER_PATTERN_RE.search(content):
        return issues

    for i, line in enumerate(lines, start=1):
        stripped = line.strip()
        if stripped.startswith("//") or stripped.startswith("*"):
            continue

        match = _DIRECT_MUTATION_RE.search(line)
        if match:
            issues.append(ASTIssue(
                file=file_path,
                line=i,
                rule="zustand_mutation",
                severity="error",
                message=(
                    f"Direct state mutation 'state.{match.group(1)}' "
                    f"in Zustand store — must use immer or set()"
                ),
                suggestion=(
                    "Use set() callback or add immer middleware: "
                    "set((state) => { state.prop = value })"
                ),
            ))

    return issues


def _find_nullable_vars(content: str) -> set[str]:
    """Find variable names declared with nullable types."""
    nullable: set[str] = set()

    for match in _NULLABLE_DECLARATIONS.finditer(content):
        nullable.add(match.group(1))

    # Also consider common patterns that produce nullable values
    # useState with null initial value
    for match in re.finditer(
        r"(?:const|let)\s+\[(\w+),\s*set\w+\]\s*=\s*useState\s*(?:<[^>]*>)?\s*\(\s*null\s*\)",
        content,
    ):
        nullable.add(match.group(1))

    # Variables assigned from optional chaining (result could be undefined)
    for match in re.finditer(
        r"(?:const|let)\s+(\w+)\s*=\s*\w+\?\.",
        content,
    ):
        nullable.add(match.group(1))

    return nullable


# ── Main entry point ─────────────────────────────────────────────────


def analyze_file(file_path: str, content: str) -> ASTReport:
    """Analyse a TypeScript/TSX file for common error patterns.

    Called inline by each build agent on its own output.
    Does NOT modify the file — reports issues only.

    Args:
        file_path: Path of the file being analysed.
        content: Full file content as a string.

    Returns:
        ASTReport with all detected issues and severity.
    """
    # Only analyse TS/JS files
    if not any(file_path.endswith(ext) for ext in _TS_EXTENSIONS):
        return ASTReport(
            file_path=file_path,
            issues=[],
            severity="warning",
            lines_analysed=0,
        )

    lines = content.split("\n")
    all_issues: list[ASTIssue] = []

    # Find nullable variables for null-ref detection
    nullable_vars = _find_nullable_vars(content)

    # Run all checks
    all_issues.extend(_check_null_references(file_path, lines, nullable_vars))
    all_issues.extend(_check_unhandled_promises(file_path, content, lines))
    all_issues.extend(_check_missing_error_boundaries(file_path, content))
    all_issues.extend(_check_zustand_mutations(file_path, content, lines))

    # Determine worst severity
    severity = "warning"
    if any(issue.severity == "error" for issue in all_issues):
        severity = "error"

    logger.info(
        "ast_analyser.completed",
        file_path=file_path,
        issues_found=len(all_issues),
        severity=severity,
        lines_analysed=len(lines),
    )

    return ASTReport(
        file_path=file_path,
        issues=all_issues,
        severity=severity,
        lines_analysed=len(lines),
    )

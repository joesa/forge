"""
Layer 6 — Error boundary injector.

Wraps every page component in a React ErrorBoundary component.
Uses ErrorBoundary from components/ui/ErrorBoundary.tsx (built by agent 3).

Called by ReviewAgent after page_agent completes.
"""

from __future__ import annotations

import re

import structlog

logger = structlog.get_logger(__name__)

# ── Detection patterns ───────────────────────────────────────────────

# Detect page-level component files
_PAGE_PATH_PATTERNS = [
    re.compile(r"/pages?/", re.IGNORECASE),
    re.compile(r"/app/.*page\.[tj]sx?$", re.IGNORECASE),
    re.compile(r"/views?/", re.IGNORECASE),
]

# Detect if file already has ErrorBoundary
_HAS_ERROR_BOUNDARY_RE = re.compile(
    r"<ErrorBoundary[\s>]|ErrorBoundary",
)

# Detect the default export
_DEFAULT_EXPORT_FUNCTION_RE = re.compile(
    r"export\s+default\s+function\s+(\w+)\s*\(",
    re.MULTILINE,
)
_DEFAULT_EXPORT_CONST_RE = re.compile(
    r"export\s+default\s+(\w+)\s*;",
    re.MULTILINE,
)

# Detect existing imports to insert after
_IMPORT_BLOCK_END_RE = re.compile(
    r"^(?:import\s.+(?:\n|$))+",
    re.MULTILINE,
)

# ErrorBoundary import line
_ERROR_BOUNDARY_IMPORT = (
    "import { ErrorBoundary } from '@/components/ui/ErrorBoundary';\n"
)


def _is_page_file(file_path: str) -> bool:
    """Check if a file path is a page-level component."""
    return any(pattern.search(file_path) for pattern in _PAGE_PATH_PATTERNS)


def _already_has_error_boundary(content: str) -> bool:
    """Check if file already references ErrorBoundary."""
    return bool(_HAS_ERROR_BOUNDARY_RE.search(content))


def _inject_into_file(content: str) -> str | None:
    """Inject ErrorBoundary wrapper into a page component file.

    Returns modified content, or None if injection is not applicable.
    """
    # Already has ErrorBoundary
    if _already_has_error_boundary(content):
        return None

    # Find the default export function
    func_match = _DEFAULT_EXPORT_FUNCTION_RE.search(content)
    if not func_match:
        return None

    component_name = func_match.group(1)

    # Step 1: Add ErrorBoundary import after the last import statement
    import_match = _IMPORT_BLOCK_END_RE.search(content)
    if import_match:
        insert_pos = import_match.end()
        content = (
            content[:insert_pos]
            + _ERROR_BOUNDARY_IMPORT
            + content[insert_pos:]
        )
    else:
        # No imports found — add at the top
        content = _ERROR_BOUNDARY_IMPORT + "\n" + content

    # Step 2: Find the return statement and wrap JSX in ErrorBoundary
    # Find `return (` or `return <` in the component
    return_pattern = re.compile(
        rf"(export\s+default\s+function\s+{re.escape(component_name)}"
        r"\s*\([^)]*\)\s*\{[^}]*?"
        r"return\s*)\(\s*\n",
        re.DOTALL,
    )

    return_match = return_pattern.search(content)
    if return_match:
        # Wrap the return content in ErrorBoundary
        return_pos = return_match.end()

        # Find the matching closing paren of return(...)
        depth = 1
        pos = return_pos
        while pos < len(content) and depth > 0:
            if content[pos] == "(":
                depth += 1
            elif content[pos] == ")":
                depth -= 1
            pos += 1

        if depth == 0:
            # pos is now right after the closing )
            inner_jsx = content[return_pos:pos - 1]

            # Determine indentation
            wrapped = (
                content[:return_pos]
                + "\n    <ErrorBoundary>\n"
                + inner_jsx
                + "\n    </ErrorBoundary>\n  "
                + content[pos - 1:]
            )
            return wrapped

    # Fallback: try simpler return <Component pattern
    simple_return = re.compile(
        r"(return\s+)(<[A-Z])",
        re.MULTILINE,
    )
    simple_match = simple_return.search(content)
    if simple_match:
        # Find the end of the JSX expression (matching the semicolon)
        start = simple_match.start()
        line_end = content.find(";", start)
        if line_end == -1:
            line_end = content.find("\n}", start)

        if line_end > start:
            jsx_content = content[simple_match.start(2):line_end].rstrip(";")
            replacement = (
                f"{simple_match.group(1)}"
                f"<ErrorBoundary>{jsx_content}</ErrorBoundary>;"
            )
            content = (
                content[:start]
                + replacement
                + content[line_end + 1:]
            )
            return content

    return None


# ── Main entry point ─────────────────────────────────────────────────


def inject_error_boundaries(
    page_files: dict[str, str],
) -> dict[str, str]:
    """Inject ErrorBoundary wrappers into page components.

    Wraps every page component's JSX return in an <ErrorBoundary> tag.
    Adds the import statement if not already present.
    Skips files that already have ErrorBoundary references.

    Args:
        page_files: Dict of file_path → file_content for all generated files.

    Returns:
        Dict of file_path → modified_content (only modified files included).
    """
    modified: dict[str, str] = {}
    injected_count = 0
    skipped_count = 0

    for file_path, content in page_files.items():
        # Only process page-level component files
        if not _is_page_file(file_path):
            continue

        # Skip files that already have ErrorBoundary
        if _already_has_error_boundary(content):
            skipped_count += 1
            continue

        result = _inject_into_file(content)
        if result is not None:
            modified[file_path] = result
            injected_count += 1
        else:
            skipped_count += 1

    logger.info(
        "error_boundary_injector.completed",
        injected=injected_count,
        skipped=skipped_count,
        total_pages=injected_count + skipped_count,
    )

    return modified

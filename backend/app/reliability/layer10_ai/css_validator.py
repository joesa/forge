"""
Layer 10 — CSS/Tailwind class validator.

Validates that className strings in generated TSX/JSX files reference
real Tailwind utility classes.  Invalid classes are flagged so the
StyleAgent can fix them before the build completes.

Approach:
1. Extract all className values from TSX/JSX files via regex
2. Split into individual classes
3. Validate each class against Tailwind's utility pattern catalogue
4. Report invalid classes grouped by file
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

import structlog

logger = structlog.get_logger(__name__)


# ── Types ────────────────────────────────────────────────────────────


@dataclass
class InvalidClass:
    """A single invalid CSS class usage."""

    class_name: str
    file_path: str
    line_number: int = 0
    context: str = ""  # Surrounding JSX for debugging


@dataclass
class CSSValidationReport:
    """Full CSS validation report."""

    passed: bool = True
    total_classes: int = 0
    invalid_classes: list[InvalidClass] = field(default_factory=list)
    by_file: dict[str, list[str]] = field(default_factory=dict)
    error: str | None = None


# ── Tailwind class patterns ──────────────────────────────────────────

# Common Tailwind v3 utility prefixes (non-exhaustive but covers most)
_TAILWIND_PREFIXES: set[str] = {
    # Layout
    "container", "columns", "break",
    "box", "block", "inline", "flex", "grid", "table", "hidden",
    "contents", "list", "flow",
    # Flexbox & Grid
    "basis", "grow", "shrink", "order",
    "col", "row", "auto", "gap", "justify", "items", "self",
    "place", "content",
    # Spacing
    "p", "px", "py", "pt", "pr", "pb", "pl", "ps", "pe",
    "m", "mx", "my", "mt", "mr", "mb", "ml", "ms", "me",
    "space",
    # Sizing
    "w", "min", "max", "h", "size",
    # Typography
    "font", "text", "antialiased", "subpixel",
    "italic", "not", "normal", "uppercase", "lowercase",
    "capitalize", "truncate", "indent", "align",
    "whitespace", "break", "hyphens",
    "leading", "tracking", "decoration", "underline",
    "overline", "line", "no",
    # Backgrounds
    "bg", "from", "via", "to", "gradient",
    # Borders
    "rounded", "border", "divide", "outline", "ring",
    # Effects
    "shadow", "opacity", "mix", "brightness", "contrast",
    "drop", "grayscale", "hue", "invert", "saturate", "sepia",
    "backdrop", "blur", "filter",
    # Transitions & Animation
    "transition", "duration", "ease", "delay", "animate",
    # Transforms
    "scale", "rotate", "translate", "skew", "origin",
    "transform",
    # Interactivity
    "accent", "appearance", "cursor", "caret", "pointer",
    "resize", "scroll", "snap", "touch", "select", "will",
    # SVG
    "fill", "stroke",
    # Accessibility
    "sr",
    # Positioning
    "static", "fixed", "absolute", "relative", "sticky",
    "inset", "top", "right", "bottom", "left", "z",
    "float", "clear", "isolate", "isolation",
    "object",
    # Visibility
    "visible", "invisible", "collapse",
    # Overflow
    "overflow", "overscroll",
    # Display
    "aspect",
}

# Responsive / state prefixes
_MODIFIER_PREFIXES: set[str] = {
    "sm", "md", "lg", "xl", "2xl",
    "hover", "focus", "active", "disabled", "visited",
    "first", "last", "odd", "even", "group", "peer",
    "dark", "motion", "print", "rtl", "ltr",
    "placeholder", "file", "marker", "selection",
    "before", "after", "first-line", "first-letter",
    "checked", "indeterminate", "required", "invalid",
    "valid", "in-range", "out-of-range", "read-only",
    "empty", "focus-within", "focus-visible",
    "aria", "data", "supports", "contrast", "forced",
    "open",
}

# Arbitrary value pattern: e.g. w-[100px], bg-[#ff0000]
_ARBITRARY_VALUE_RE = re.compile(r"^[a-z]+-\[.+\]$")

# Negative value pattern: e.g. -mt-4, -translate-x-1/2
_NEGATIVE_PREFIX_RE = re.compile(r"^-[a-z]")

# Special standalone classes that are valid
_STANDALONE_CLASSES: set[str] = {
    "container", "prose", "antialiased", "subpixel-antialiased",
    "truncate", "italic", "not-italic", "uppercase", "lowercase",
    "capitalize", "normal-case", "ordinal", "slashed-zero",
    "lining-nums", "oldstyle-nums", "proportional-nums", "tabular-nums",
    "diagonal-fractions", "stacked-fractions",
    "underline", "overline", "line-through", "no-underline",
    "sr-only", "not-sr-only",
    "visible", "invisible", "collapse",
    "static", "fixed", "absolute", "relative", "sticky",
    "isolate", "isolation-auto",
    "block", "inline-block", "inline", "flex", "inline-flex",
    "table", "inline-table", "table-caption", "table-cell",
    "table-column", "table-column-group", "table-footer-group",
    "table-header-group", "table-row-group", "table-row",
    "flow-root", "grid", "inline-grid", "contents", "list-item",
    "hidden",
    "grow", "grow-0", "shrink", "shrink-0",
    "transition", "transform",
}


def _is_valid_tailwind_class(class_name: str) -> bool:
    """Check if a class name looks like a valid Tailwind utility.

    This is a heuristic check — not an exhaustive Tailwind compiler.
    """
    if not class_name or not class_name.strip():
        return True  # Empty = skip

    name = class_name.strip()

    # Standalone classes
    if name in _STANDALONE_CLASSES:
        return True

    # Strip modifier prefixes (hover:, sm:, dark:, etc.)
    base = name
    while ":" in base:
        prefix, _, rest = base.partition(":")
        if prefix.lstrip("!") in _MODIFIER_PREFIXES:
            base = rest
        else:
            break

    # Strip important prefix (!)
    if base.startswith("!"):
        base = base[1:]

    if not base:
        return False

    # Check standalone again after stripping modifiers
    if base in _STANDALONE_CLASSES:
        return True

    # Arbitrary value pattern: w-[100px]
    if _ARBITRARY_VALUE_RE.match(base):
        return True

    # Negative prefix: -mt-4
    check_base = base
    if _NEGATIVE_PREFIX_RE.match(base):
        check_base = base[1:]

    # Extract the main prefix (before the first dash)
    parts = check_base.split("-")
    prefix = parts[0]

    return prefix in _TAILWIND_PREFIXES


# ── Class extraction ─────────────────────────────────────────────────

# className="..." or className='...' or className={`...`}
_CLASSNAME_RE = re.compile(
    r'className\s*=\s*["\']([^"\']+)["\']'
    r"|"
    r"className\s*=\s*\{`([^`]+)`\}",
    re.MULTILINE,
)

# clsx/cn/classNames/twMerge calls: cn("...", "...")
_CN_CALL_RE = re.compile(
    r'(?:cn|clsx|classNames|twMerge)\s*\(\s*["\']([^"\']+)["\']',
    re.MULTILINE,
)


def _extract_classes_from_file(
    file_path: str,
    content: str,
) -> list[tuple[str, int]]:
    """Extract all CSS class names from a TSX/JSX file.

    Returns list of (class_name, line_number) tuples.
    """
    results: list[tuple[str, int]] = []

    lines = content.split("\n")
    for line_num, line in enumerate(lines, 1):
        # className="..." patterns
        for match in _CLASSNAME_RE.finditer(line):
            class_str = match.group(1) or match.group(2) or ""
            for cls in class_str.split():
                results.append((cls, line_num))

        # cn("...") / clsx("...") patterns
        for match in _CN_CALL_RE.finditer(line):
            class_str = match.group(1) or ""
            for cls in class_str.split():
                results.append((cls, line_num))

    return results


# ── Public API ───────────────────────────────────────────────────────


async def validate_css_classes(
    generated_files: dict[str, str],
) -> CSSValidationReport:
    """Validate CSS/Tailwind class usage in generated TSX/JSX files.

    Parameters
    ----------
    generated_files : dict[str, str]
        Mapping of file paths to file contents.

    Returns
    -------
    CSSValidationReport
        Report with invalid classes grouped by file.
    """
    report = CSSValidationReport()

    if not generated_files:
        report.error = "No files provided for validation"
        report.passed = False
        return report

    try:
        # Only check TSX/JSX files
        tsx_files = {
            path: content
            for path, content in generated_files.items()
            if path.endswith((".tsx", ".jsx"))
        }

        if not tsx_files:
            # No TSX files — nothing to validate, pass
            logger.info("css_validator.no_tsx_files")
            return report

        for file_path, content in tsx_files.items():
            classes = _extract_classes_from_file(file_path, content)
            report.total_classes += len(classes)

            file_invalid: list[str] = []
            for class_name, line_num in classes:
                if not _is_valid_tailwind_class(class_name):
                    invalid = InvalidClass(
                        class_name=class_name,
                        file_path=file_path,
                        line_number=line_num,
                    )
                    report.invalid_classes.append(invalid)
                    file_invalid.append(class_name)

            if file_invalid:
                report.by_file[file_path] = file_invalid

        report.passed = len(report.invalid_classes) == 0

        logger.info(
            "css_validator.complete",
            total_classes=report.total_classes,
            invalid=len(report.invalid_classes),
            files_checked=len(tsx_files),
            passed=report.passed,
        )

    except Exception as exc:
        report.passed = False
        report.error = str(exc)
        logger.error("css_validator.failed", error=str(exc))

    return report

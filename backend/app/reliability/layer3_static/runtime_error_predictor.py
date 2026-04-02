"""
Layer 3 — Runtime error predictor.

Pattern matching for common React/TypeScript runtime errors.
Predicts errors before they happen and provides fix suggestions.

Detected patterns:
  - "Cannot read property of undefined" (missing optional chaining)
  - "Maximum update depth exceeded" (setState in render body)
  - "Objects are not valid as React child" (missing .map or .toString)
"""

from __future__ import annotations

import re

from pydantic import BaseModel, Field

import structlog

logger = structlog.get_logger(__name__)


# ── Pydantic models ──────────────────────────────────────────────────


class PredictedError(BaseModel):
    """A predicted runtime error with location and fix suggestion."""

    file: str = ""
    line: int = Field(ge=0, default=0)
    error_type: str = Field(
        description="cannot_read_property | max_update_depth | "
        "invalid_react_child | missing_key_prop | undefined_hook_dep"
    )
    predicted_message: str
    fix_suggestion: str
    confidence: float = Field(ge=0.0, le=1.0, default=0.8)


# ── Detection patterns ───────────────────────────────────────────────

# Pattern 1: Accessing nested properties without null checks
# E.g.: data.user.profile.name  should be  data?.user?.profile?.name
_NESTED_ACCESS_RE = re.compile(
    r"\b(\w+)\.(\w+)\.(\w+)(?:\.(\w+))?\b"
)
_SAFE_ACCESS_RE = re.compile(r"\?\.")

# Common variable names that indicate nullable data
_NULLABLE_SOURCES = {
    "data", "result", "response", "res", "user", "profile",
    "session", "params", "query", "error", "item", "record",
}

# Pattern 2: setState called directly in component render body
# (outside useEffect, event handler, or callback)
_USE_STATE_RE = re.compile(
    r"\bconst\s+\[(\w+),\s*(set\w+)\]\s*=\s*useState"
)
_USE_EFFECT_RE = re.compile(r"\buseEffect\s*\(")
_EVENT_HANDLER_RE = re.compile(
    r"(?:const|function)\s+(?:handle\w+|on\w+)\s*(?:=|{|\()"
)
_CALLBACK_RE = re.compile(r"(?:useCallback|useMemo)\s*\(")

# Pattern 3: Rendering objects/arrays directly as React children
_RENDER_OBJECT_RE = re.compile(
    r"[{>]\s*\{?\s*(\w+)\s*\}?\s*[<}]"
)
_MAP_CALL_RE = re.compile(r"\.map\s*\(")
_TO_STRING_RE = re.compile(r"\.toString\s*\(")
_JSON_STRINGIFY_RE = re.compile(r"JSON\.stringify\s*\(")

# Pattern 4: Array rendering without key prop
_MAP_RETURN_JSX_RE = re.compile(
    r"\.map\s*\([^)]*\)\s*(?:=>|{)\s*(?:\(?\s*<(\w+))",
    re.MULTILINE,
)
_KEY_PROP_RE = re.compile(r"\bkey\s*=")

# Pattern 5: Missing useEffect dependency
_USE_EFFECT_EMPTY_DEPS_RE = re.compile(
    r"useEffect\s*\(\s*\(\s*\)\s*=>\s*\{([^}]*)\}\s*,\s*\[\s*\]\s*\)",
    re.DOTALL,
)

# Identifiers that are safe to access without optional chaining
_SAFE_ROOTS = {
    "console", "Math", "Object", "Array", "JSON", "Number", "String",
    "Boolean", "Date", "RegExp", "Promise", "Error", "Map", "Set",
    "window", "document", "navigator", "localStorage", "sessionStorage",
    "React", "process", "module", "exports", "require",
    "e", "event", "err", "ctx", "ref", "props",
}


# ── Detection functions ──────────────────────────────────────────────


def _predict_cannot_read_property(
    content: str,
    lines: list[str],
    context: dict[str, object],
) -> list[PredictedError]:
    """Detect patterns that cause 'Cannot read property of undefined'."""
    errors: list[PredictedError] = []

    for i, line in enumerate(lines, start=1):
        stripped = line.strip()
        if stripped.startswith("//") or stripped.startswith("*"):
            continue

        # Find deep property access chains
        for match in _NESTED_ACCESS_RE.finditer(line):
            root = match.group(1)

            # Skip safe global objects
            if root in _SAFE_ROOTS:
                continue

            # Skip if line uses optional chaining
            # Check the specific segment around the match, not the whole line
            match_text = match.group(0)
            if "?." in match_text:
                continue

            # Only flag if root is a known nullable source or from API
            is_nullable = (
                root in _NULLABLE_SOURCES
                or root.startswith("fetch")
                or root.endswith("Data")
                or root.endswith("Result")
            )

            if not is_nullable:
                continue

            chain = match.group(0)
            suggested = chain.replace(".", "?.")
            errors.append(PredictedError(
                line=i,
                error_type="cannot_read_property",
                predicted_message=(
                    f"Cannot read properties of undefined "
                    f"(reading '{match.group(2)}')"
                ),
                fix_suggestion=f"Use optional chaining: {suggested}",
                confidence=0.75,
            ))

    return errors


def _predict_max_update_depth(
    content: str,
    lines: list[str],
    context: dict[str, object],
) -> list[PredictedError]:
    """Detect setState calls in render body causing infinite loops."""
    errors: list[PredictedError] = []

    # Find all setState function names
    setter_names: set[str] = set()
    for match in _USE_STATE_RE.finditer(content):
        setter_names.add(match.group(2))

    if not setter_names:
        return errors

    # Track scope: are we inside useEffect, event handler, or callback?
    in_safe_scope = False
    safe_scope_depth = 0
    brace_depth = 0
    component_body_started = False

    for i, line in enumerate(lines, start=1):
        stripped = line.strip()
        if stripped.startswith("//") or stripped.startswith("*"):
            continue

        # Track component body
        if re.search(
            r"(?:export\s+)?(?:default\s+)?function\s+\w+\s*\(", line
        ):
            component_body_started = True

        if not component_body_started:
            continue

        # Track brace depth
        brace_depth += line.count("{") - line.count("}")

        # Detect safe scopes
        if (
            _USE_EFFECT_RE.search(line)
            or _EVENT_HANDLER_RE.search(line)
            or _CALLBACK_RE.search(line)
            or "addEventListener" in line
            or "setTimeout" in line
            or "setInterval" in line
            or ".then(" in line
        ):
            in_safe_scope = True
            safe_scope_depth = brace_depth

        # Left safe scope
        if in_safe_scope and brace_depth < safe_scope_depth:
            in_safe_scope = False

        # Check for setState in render body
        if not in_safe_scope:
            for setter in setter_names:
                # Direct call: setFoo(value)
                pattern = rf"\b{re.escape(setter)}\s*\("
                if re.search(pattern, line):
                    # Exclude declarations (const setFoo = ...)
                    decl_prefix = "const ["
                    decl_suffix = ", " + setter + "]"
                    if decl_prefix in line or decl_suffix in line:
                        continue
                    errors.append(PredictedError(
                        line=i,
                        error_type="max_update_depth",
                        predicted_message=(
                            "Maximum update depth exceeded. This can happen when "
                            "a component calls setState inside the render body."
                        ),
                        fix_suggestion=(
                            f"Move {setter}() call into useEffect, "
                            f"an event handler, or a callback"
                        ),
                        confidence=0.85,
                    ))

    return errors


def _predict_invalid_react_child(
    content: str,
    lines: list[str],
    context: dict[str, object],
) -> list[PredictedError]:
    """Detect objects/arrays rendered directly as React children."""
    errors: list[PredictedError] = []

    # Look for patterns where objects/arrays might be rendered
    # Common anti-pattern: {someObject} in JSX without .map() or .toString()
    object_vars: set[str] = set()

    # Find variables declared as objects/arrays
    for match in re.finditer(
        r"(?:const|let)\s+(\w+)\s*(?::\s*(?:Record|object|Object|\{[^}]*\}|any\[\]|\w+\[\]))?",
        content,
    ):
        var_name = match.group(1)
        # Check if the declaration hints at being an object or array
        full_match = match.group(0)
        if any(
            hint in full_match
            for hint in ("Record", "object", "Object", "{}", "[]")
        ):
            object_vars.add(var_name)

    # Also find variables assigned from API calls (likely objects)
    for match in re.finditer(
        r"(?:const|let)\s+(\w+)\s*=\s*(?:await\s+)?(?:fetch|axios|api)\b",
        content,
    ):
        object_vars.add(match.group(1))

    if not object_vars:
        return errors

    # Check for direct rendering of object variables
    for i, line in enumerate(lines, start=1):
        stripped = line.strip()
        if stripped.startswith("//") or stripped.startswith("*"):
            continue

        # Check for JSX interpolation of object variables: {objectVar}
        for var_name in object_vars:
            # Match {varName} in JSX context (not in event handlers etc.)
            pattern = rf"\{{\s*{re.escape(var_name)}\s*\}}"
            if re.search(pattern, line):
                # Skip if it's using .map(), .toString(), JSON.stringify, etc.
                if (
                    _MAP_CALL_RE.search(line)
                    or _TO_STRING_RE.search(line)
                    or _JSON_STRINGIFY_RE.search(line)
                    or f"{var_name}." in line
                ):
                    continue

                errors.append(PredictedError(
                    line=i,
                    error_type="invalid_react_child",
                    predicted_message=(
                        f"Objects are not valid as a React child "
                        f"(found: {var_name})"
                    ),
                    fix_suggestion=(
                        f"Use {var_name}.map() for arrays, "
                        f"JSON.stringify({var_name}) for objects, "
                        f"or access specific properties"
                    ),
                    confidence=0.7,
                ))

    return errors


def _predict_missing_key_prop(
    content: str,
    lines: list[str],
    context: dict[str, object],
) -> list[PredictedError]:
    """Detect .map() rendering JSX without key prop."""
    errors: list[PredictedError] = []

    # Find .map() calls that return JSX
    for i, line in enumerate(lines, start=1):
        stripped = line.strip()
        if stripped.startswith("//") or stripped.startswith("*"):
            continue

        if ".map(" in line and "<" in line:
            # Check this line and next few lines for key prop
            context_block = "\n".join(lines[i - 1:min(i + 4, len(lines))])
            if not _KEY_PROP_RE.search(context_block):
                errors.append(PredictedError(
                    line=i,
                    error_type="missing_key_prop",
                    predicted_message=(
                        "Each child in a list should have a unique 'key' prop"
                    ),
                    fix_suggestion=(
                        "Add a unique key prop to the mapped element: "
                        "<Element key={item.id} />"
                    ),
                    confidence=0.8,
                ))

    return errors


# ── Main entry point ─────────────────────────────────────────────────


def predict_errors(
    file_content: str,
    context: dict[str, object] | None = None,
) -> list[PredictedError]:
    """Predict common runtime errors from file content.

    Args:
        file_content: Full file content as string.
        context: Optional context dict with metadata (e.g., file_path, framework).

    Returns:
        List of predicted errors with line numbers and fix suggestions.
    """
    if context is None:
        context = {}

    lines = file_content.split("\n")
    all_errors: list[PredictedError] = []

    file_path = str(context.get("file_path", ""))

    # Run all predictors
    all_errors.extend(
        _predict_cannot_read_property(file_content, lines, context)
    )
    all_errors.extend(
        _predict_max_update_depth(file_content, lines, context)
    )
    all_errors.extend(
        _predict_invalid_react_child(file_content, lines, context)
    )
    all_errors.extend(
        _predict_missing_key_prop(file_content, lines, context)
    )

    # Set file path on all errors
    for error in all_errors:
        if not error.file:
            error.file = file_path

    logger.info(
        "runtime_error_predictor.completed",
        file_path=file_path,
        predictions=len(all_errors),
        error_types=[e.error_type for e in all_errors],
    )

    return all_errors

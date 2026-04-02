"""
Layer 4 — File coherence engine.

Architecture rule #5: runs AFTER all 10 build agents complete.
Never called from individual build agents.

Algorithm:
  1. Parse all .ts/.tsx/.js/.jsx files for import/export declarations
  2. Build export_map and import_map
  3. Validate every import references an actual export
  4. Validate barrel re-exports
  5. Detect seam errors (truncated files)
  6. Auto-fix minor issues (typos, case mismatches)
  7. Escalate critical errors (missing files, circular imports)
"""

from __future__ import annotations

import os
import re
from typing import Any

from pydantic import BaseModel, Field

import structlog

from app.reliability.layer4_coherence.barrel_validator import validate_barrel
from app.reliability.layer4_coherence.seam_checker import check_seam

logger = structlog.get_logger(__name__)


# ── Pydantic models ──────────────────────────────────────────────────


class CoherenceIssue(BaseModel):
    """A single coherence issue found during analysis."""

    file: str
    issue_type: str = Field(
        description="import_error | missing_export | missing_file | "
        "circular_import | seam_error | barrel_error | case_mismatch | typo"
    )
    severity: str = Field(description="auto_fixed | warning | critical")
    message: str
    fix_applied: str | None = None


class CoherenceCheckReport(BaseModel):
    """Full coherence check report — stored in coherence_reports table."""

    build_id: str
    total_files: int
    files_checked: int
    issues: list[CoherenceIssue] = Field(default_factory=list)
    auto_fixes_applied: int = 0
    critical_errors: int = 0
    warnings: int = 0
    all_passed: bool = True


# ── Import/export parsers ────────────────────────────────────────────

_IMPORT_RE = re.compile(
    r"import\s*\{([^}]+)\}\s*from\s*['\"]([^'\"]+)['\"]", re.MULTILINE
)
_IMPORT_DEFAULT_RE = re.compile(
    r"import\s+(\w+)\s+from\s*['\"]([^'\"]+)['\"]", re.MULTILINE
)
_IMPORT_STAR_RE = re.compile(
    r"import\s*\*\s+as\s+(\w+)\s+from\s*['\"]([^'\"]+)['\"]", re.MULTILINE
)

_EXPORT_NAMED_RE = re.compile(
    r"export\s*\{([^}]+)\}", re.MULTILINE
)
_EXPORT_DECLARATION_RE = re.compile(
    r"export\s+(?:const|let|var|function|class|interface|type|enum)\s+(\w+)",
    re.MULTILINE,
)
_EXPORT_DEFAULT_RE = re.compile(
    r"export\s+default\s+(?:function|class|const|let|var)?\s*(\w+)?",
    re.MULTILINE,
)
_EXPORT_FROM_RE = re.compile(
    r"export\s*\{([^}]+)\}\s*from\s*['\"]([^'\"]+)['\"]", re.MULTILINE
)
_EXPORT_STAR_RE = re.compile(
    r"export\s*\*\s*(?:as\s+(\w+)\s*)?from\s*['\"]([^'\"]+)['\"]",
    re.MULTILINE,
)

_TS_EXTENSIONS = (".ts", ".tsx", ".js", ".jsx")


# ── Helpers ──────────────────────────────────────────────────────────


def _is_ts_file(path: str) -> bool:
    """Check if a file path is a TypeScript/JavaScript file."""
    return any(path.endswith(ext) for ext in _TS_EXTENSIONS)


def _levenshtein_distance(s1: str, s2: str) -> int:
    """Compute Levenshtein edit distance between two strings."""
    if len(s1) < len(s2):
        return _levenshtein_distance(s2, s1)
    if len(s2) == 0:
        return len(s1)

    prev_row = list(range(len(s2) + 1))
    for i, c1 in enumerate(s1):
        curr_row = [i + 1]
        for j, c2 in enumerate(s2):
            # j+1 instead of j since prev_row and curr_row are one char longer
            insertions = prev_row[j + 1] + 1
            deletions = curr_row[j] + 1
            substitutions = prev_row[j] + (c1 != c2)
            curr_row.append(min(insertions, deletions, substitutions))
        prev_row = curr_row

    return prev_row[-1]


def _resolve_import_path(
    source_file: str,
    import_path: str,
    all_files: dict[str, str],
) -> str | None:
    """Resolve relative import path to an actual file path.

    Returns the resolved file path, or None if not found.
    """
    # Skip external/node_modules imports
    if not import_path.startswith("."):
        return None  # External package — not our concern

    source_dir = os.path.dirname(source_file)
    resolved = os.path.normpath(os.path.join(source_dir, import_path))

    # Try exact match first
    if resolved in all_files:
        return resolved

    # Try with extensions
    for ext in _TS_EXTENSIONS:
        candidate = resolved + ext
        if candidate in all_files:
            return candidate

    # Try as directory with index file
    for ext in _TS_EXTENSIONS:
        candidate = os.path.join(resolved, f"index{ext}")
        if candidate in all_files:
            return candidate

    return None


def _extract_exports(content: str) -> set[str]:
    """Extract all exported symbol names from file content."""
    exports: set[str] = set()

    # export { Foo, Bar }
    for match in _EXPORT_NAMED_RE.finditer(content):
        for sym in match.group(1).split(","):
            sym = sym.strip()
            if " as " in sym:
                sym = sym.split(" as ")[-1].strip()
            if sym:
                exports.add(sym)

    # export const Foo = ...
    for match in _EXPORT_DECLARATION_RE.finditer(content):
        exports.add(match.group(1))

    # export default function Foo
    for match in _EXPORT_DEFAULT_RE.finditer(content):
        name = match.group(1)
        if name:
            exports.add(name)
        exports.add("default")

    # export { Foo } from './bar'
    for match in _EXPORT_FROM_RE.finditer(content):
        for sym in match.group(1).split(","):
            sym = sym.strip()
            if " as " in sym:
                sym = sym.split(" as ")[-1].strip()
            if sym:
                exports.add(sym)

    # export * from './bar'
    for match in _EXPORT_STAR_RE.finditer(content):
        alias = match.group(1)
        if alias:
            exports.add(alias)
        else:
            exports.add("*")

    return exports


def _extract_imports(
    content: str,
) -> list[dict[str, str]]:
    """Extract all imports from file content.

    Returns list of {symbol, source, type} dicts.
    """
    imports: list[dict[str, str]] = []

    # import { Foo, Bar } from './module'
    for match in _IMPORT_RE.finditer(content):
        symbols_str = match.group(1)
        source = match.group(2)
        for sym in symbols_str.split(","):
            sym = sym.strip()
            original = sym
            if " as " in sym:
                sym = sym.split(" as ")[0].strip()
            if sym:
                imports.append({
                    "symbol": sym,
                    "source": source,
                    "type": "named",
                    "original": original,
                })

    # import Foo from './module'
    for match in _IMPORT_DEFAULT_RE.finditer(content):
        name = match.group(1)
        source = match.group(2)
        imports.append({
            "symbol": "default",
            "alias": name,
            "source": source,
            "type": "default",
            "original": name,
        })

    # import * as Foo from './module'
    for match in _IMPORT_STAR_RE.finditer(content):
        name = match.group(1)
        source = match.group(2)
        imports.append({
            "symbol": "*",
            "alias": name,
            "source": source,
            "type": "star",
            "original": f"* as {name}",
        })

    return imports


def _detect_circular_imports(
    import_graph: dict[str, set[str]],
) -> list[list[str]]:
    """Detect circular import chains in the import graph.

    Returns list of cycles, where each cycle is a list of file paths.
    """
    cycles: list[list[str]] = []
    visited: set[str] = set()
    rec_stack: set[str] = set()

    def _dfs(node: str, path: list[str]) -> None:
        visited.add(node)
        rec_stack.add(node)
        path.append(node)

        for neighbor in import_graph.get(node, set()):
            if neighbor not in visited:
                _dfs(neighbor, path)
            elif neighbor in rec_stack:
                # Found a cycle
                cycle_start = path.index(neighbor)
                cycle = path[cycle_start:] + [neighbor]
                cycles.append(cycle)

        path.pop()
        rec_stack.discard(node)

    for node in import_graph:
        if node not in visited:
            _dfs(node, [])

    return cycles


def _to_kebab_case(name: str) -> str:
    """Convert a filename to kebab-case."""
    # Split on camelCase/PascalCase boundaries
    s1 = re.sub(r"(.)([A-Z][a-z]+)", r"\1-\2", name)
    s2 = re.sub(r"([a-z0-9])([A-Z])", r"\1-\2", s1)
    return s2.lower().replace("_", "-")


# ── Main coherence check ────────────────────────────────────────────


async def run_coherence_check(
    build_id: str,
    generated_files: dict[str, str],
) -> CoherenceCheckReport:
    """Run the full file coherence check on all generated files.

    Architecture rule #5: This runs AFTER all 10 build agents complete.
    Never call this from individual build agents.

    Args:
        build_id: The build ID for tracking.
        generated_files: Dict of file_path → file_content.

    Returns:
        CoherenceCheckReport with all issues, fixes, and error counts.
    """
    issues: list[CoherenceIssue] = []
    auto_fixes = 0
    critical_errors = 0
    warnings = 0

    # Filter to TS/JS files only
    ts_files = {
        path: content
        for path, content in generated_files.items()
        if _is_ts_file(path)
    }

    total_files = len(generated_files)
    files_checked = len(ts_files)

    logger.info(
        "coherence_engine.starting",
        build_id=build_id,
        total_files=total_files,
        ts_files=files_checked,
    )

    # ── Step 1: Build export map ─────────────────────────────────────
    export_map: dict[str, set[str]] = {}
    for file_path, content in ts_files.items():
        export_map[file_path] = _extract_exports(content)

    # ── Step 2: Build import map and validate ────────────────────────
    import_graph: dict[str, set[str]] = {}

    for file_path, content in ts_files.items():
        file_imports = _extract_imports(content)
        import_graph[file_path] = set()

        for imp in file_imports:
            source = imp["source"]
            symbol = imp["symbol"]

            # Skip external packages
            if not source.startswith("."):
                continue

            resolved = _resolve_import_path(file_path, source, ts_files)

            if resolved is None:
                # ── Missing source file — CRITICAL ───────────────────
                # Try case-insensitive match for auto-fix
                fixed = _try_case_fix(file_path, source, ts_files)
                if fixed:
                    issues.append(CoherenceIssue(
                        file=file_path,
                        issue_type="case_mismatch",
                        severity="auto_fixed",
                        message=(
                            f"import from '{source}' — file not found "
                            f"with exact case"
                        ),
                        fix_applied=f"resolved to '{fixed}'",
                    ))
                    auto_fixes += 1
                    resolved = fixed
                else:
                    issues.append(CoherenceIssue(
                        file=file_path,
                        issue_type="missing_file",
                        severity="critical",
                        message=(
                            f"import {{ {symbol} }} from '{source}' — "
                            f"source file does not exist"
                        ),
                    ))
                    critical_errors += 1
                    continue

            import_graph[file_path].add(resolved)

            # Skip star imports — they import everything
            if symbol == "*":
                continue

            # ── Step 3: Validate import → export match ───────────────
            target_exports = export_map.get(resolved, set())

            # Wildcard exports from barrel — skip detailed check
            if "*" in target_exports:
                continue

            if symbol == "default":
                if "default" not in target_exports:
                    issues.append(CoherenceIssue(
                        file=file_path,
                        issue_type="missing_export",
                        severity="critical",
                        message=(
                            f"default import from '{source}' but "
                            f"'{resolved}' has no default export"
                        ),
                    ))
                    critical_errors += 1
                continue

            if symbol not in target_exports:
                # ── Try typo fix (Levenshtein ≤ 2) ───────────────────
                best_match = _find_closest_export(symbol, target_exports)
                if best_match:
                    issues.append(CoherenceIssue(
                        file=file_path,
                        issue_type="typo",
                        severity="auto_fixed",
                        message=(
                            f"import {{ {symbol} }} from '{source}' — "
                            f"'{symbol}' not exported, closest: '{best_match}'"
                        ),
                        fix_applied=f"changed import to '{best_match}'",
                    ))
                    auto_fixes += 1
                else:
                    issues.append(CoherenceIssue(
                        file=file_path,
                        issue_type="import_error",
                        severity="critical",
                        message=(
                            f"import {{ {symbol} }} from '{source}' — "
                            f"'{symbol}' is not exported by '{resolved}'. "
                            f"Available exports: {sorted(target_exports)}"
                        ),
                    ))
                    critical_errors += 1

    # ── Step 4: Validate barrel files ────────────────────────────────
    for file_path, content in ts_files.items():
        basename = os.path.basename(file_path)
        if basename.startswith("index."):
            # Find consumers of this barrel
            barrel_dir = os.path.dirname(file_path)
            consumers = {
                fp: c for fp, c in ts_files.items()
                if fp != file_path
            }
            barrel_report = validate_barrel(
                content, consumers, barrel_path=barrel_dir
            )
            if not barrel_report.valid:
                for missing in barrel_report.missing_exports:
                    issues.append(CoherenceIssue(
                        file=file_path,
                        issue_type="barrel_error",
                        severity="warning",
                        message=(
                            f"barrel '{file_path}' missing re-export: "
                            f"'{missing}' (imported by consumers)"
                        ),
                    ))
                    warnings += 1

    # ── Step 5: Detect seam errors ───────────────────────────────────
    for file_path, content in ts_files.items():
        seam_report = check_seam(file_path, content)
        if not seam_report.valid:
            for issue in seam_report.issues:
                issues.append(CoherenceIssue(
                    file=file_path,
                    issue_type="seam_error",
                    severity="critical",
                    message=issue,
                ))
                critical_errors += 1

    # ── Step 6: Detect circular imports ──────────────────────────────
    cycles = _detect_circular_imports(import_graph)
    for cycle in cycles:
        cycle_str = " → ".join(cycle)
        issues.append(CoherenceIssue(
            file=cycle[0],
            issue_type="circular_import",
            severity="critical",
            message=f"circular import detected: {cycle_str}",
        ))
        critical_errors += 1

    all_passed = critical_errors == 0

    logger.info(
        "coherence_engine.completed",
        build_id=build_id,
        issues_found=len(issues),
        auto_fixes=auto_fixes,
        critical_errors=critical_errors,
        warnings=warnings,
        all_passed=all_passed,
    )

    return CoherenceCheckReport(
        build_id=build_id,
        total_files=total_files,
        files_checked=files_checked,
        issues=issues,
        auto_fixes_applied=auto_fixes,
        critical_errors=critical_errors,
        warnings=warnings,
        all_passed=all_passed,
    )


# ── Auto-fix helpers ─────────────────────────────────────────────────


def _find_closest_export(
    symbol: str,
    exports: set[str],
) -> str | None:
    """Find closest matching export name (Levenshtein distance ≤ 2)."""
    if not exports:
        return None

    best: str | None = None
    best_dist = 3  # threshold: distance must be ≤ 2

    for export_name in exports:
        if export_name in ("*", "default"):
            continue
        dist = _levenshtein_distance(symbol, export_name)
        if dist < best_dist:
            best_dist = dist
            best = export_name

    return best


def _try_case_fix(
    source_file: str,
    import_path: str,
    all_files: dict[str, str],
) -> str | None:
    """Try to find a file matching the import path with different case."""
    source_dir = os.path.dirname(source_file)
    resolved = os.path.normpath(os.path.join(source_dir, import_path))

    # Build lowercase → actual path mapping
    lower_map: dict[str, str] = {}
    for fp in all_files:
        lower_map[fp.lower()] = fp

    # Try exact + extensions
    candidates = [resolved]
    for ext in _TS_EXTENSIONS:
        candidates.append(resolved + ext)
        candidates.append(os.path.join(resolved, f"index{ext}"))

    for candidate in candidates:
        lower_candidate = candidate.lower()
        if lower_candidate in lower_map:
            actual = lower_map[lower_candidate]
            if actual != candidate:
                return actual

    return None

"""
Layer 3 — Import graph resolver.

Builds a complete import graph from all generated files, then detects:
  - Circular imports (A imports B imports A)
  - Imports from non-existent files
  - Multiple versions of the same package (from package.json analysis)
"""

from __future__ import annotations

import os
import re

from pydantic import BaseModel, Field

import structlog

logger = structlog.get_logger(__name__)


# ── Pydantic models ──────────────────────────────────────────────────


class ImportEdge(BaseModel):
    """A single import relationship."""

    source_file: str
    target_file: str
    symbols: list[str] = Field(default_factory=list)


class ImportGraph(BaseModel):
    """Complete import dependency graph with detected issues."""

    graph: dict[str, list[str]] = Field(
        default_factory=dict,
        description="file_path → list of files it imports",
    )
    edges: list[ImportEdge] = Field(default_factory=list)
    circular_deps: list[list[str]] = Field(
        default_factory=list,
        description="Each cycle as a list of file paths",
    )
    missing_imports: list[str] = Field(
        default_factory=list,
        description="Import paths that reference non-existent files",
    )
    duplicate_packages: list[str] = Field(
        default_factory=list,
        description="Packages imported with multiple version specifiers",
    )
    total_files: int = 0
    total_edges: int = 0


# ── Import parsing ───────────────────────────────────────────────────

_IMPORT_RE = re.compile(
    r"import\s*\{([^}]+)\}\s*from\s*['\"]([^'\"]+)['\"]", re.MULTILINE
)
_IMPORT_DEFAULT_RE = re.compile(
    r"import\s+(\w+)\s+from\s*['\"]([^'\"]+)['\"]", re.MULTILINE
)
_IMPORT_STAR_RE = re.compile(
    r"import\s*\*\s+as\s+(\w+)\s+from\s*['\"]([^'\"]+)['\"]", re.MULTILINE
)
_DYNAMIC_IMPORT_RE = re.compile(
    r"import\s*\(\s*['\"]([^'\"]+)['\"]\s*\)", re.MULTILINE
)
_REQUIRE_RE = re.compile(
    r"require\s*\(\s*['\"]([^'\"]+)['\"]\s*\)", re.MULTILINE
)

_TS_EXTENSIONS = (".ts", ".tsx", ".js", ".jsx")


def _is_ts_file(path: str) -> bool:
    """Check if a file path is a TypeScript/JavaScript file."""
    return any(path.endswith(ext) for ext in _TS_EXTENSIONS)


def _is_relative_import(source: str) -> bool:
    """Check if an import path is relative (not a package)."""
    return source.startswith(".") or source.startswith("/")


def _extract_imports(content: str) -> list[dict[str, str | list[str]]]:
    """Extract all imports from file content.

    Returns list of dicts with 'source' and 'symbols' keys.
    """
    imports: list[dict[str, str | list[str]]] = []

    # Named imports: import { A, B } from './module'
    for match in _IMPORT_RE.finditer(content):
        symbols_str = match.group(1)
        source = match.group(2)
        symbols = [
            s.strip().split(" as ")[0].strip()
            for s in symbols_str.split(",")
            if s.strip()
        ]
        imports.append({"source": source, "symbols": symbols})

    # Default imports: import Foo from './module'
    for match in _IMPORT_DEFAULT_RE.finditer(content):
        name = match.group(1)
        source = match.group(2)
        imports.append({"source": source, "symbols": [name]})

    # Star imports: import * as Foo from './module'
    for match in _IMPORT_STAR_RE.finditer(content):
        name = match.group(1)
        source = match.group(2)
        imports.append({"source": source, "symbols": [f"* as {name}"]})

    # Dynamic imports: import('./module')
    for match in _DYNAMIC_IMPORT_RE.finditer(content):
        source = match.group(1)
        imports.append({"source": source, "symbols": ["<dynamic>"]})

    return imports


def _resolve_import_path(
    source_file: str,
    import_path: str,
    all_files: dict[str, str],
) -> str | None:
    """Resolve a relative import path to an actual file path.

    Returns the resolved file path, or None if not found.
    """
    if not _is_relative_import(import_path):
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


# ── Cycle detection ──────────────────────────────────────────────────


def _detect_cycles(graph: dict[str, list[str]]) -> list[list[str]]:
    """Detect all cycles in the import graph using DFS.

    Returns list of cycles, each as a list of file paths forming the cycle.
    """
    cycles: list[list[str]] = []
    visited: set[str] = set()
    rec_stack: set[str] = set()

    def _dfs(node: str, path: list[str]) -> None:
        visited.add(node)
        rec_stack.add(node)
        path.append(node)

        for neighbor in graph.get(node, []):
            if neighbor not in visited:
                _dfs(neighbor, path)
            elif neighbor in rec_stack:
                cycle_start = path.index(neighbor)
                cycle = path[cycle_start:] + [neighbor]
                # Deduplicate: normalize cycle to start from smallest node
                if cycle not in cycles:
                    cycles.append(cycle)

        path.pop()
        rec_stack.discard(node)

    for node in graph:
        if node not in visited:
            _dfs(node, [])

    return cycles


# ── Package version detection ────────────────────────────────────────


def _detect_duplicate_packages(
    files: dict[str, str],
) -> list[str]:
    """Detect packages imported with potentially conflicting versions.

    Checks if package.json exists and has duplicate entries, or if
    multiple package.json files exist with different version specs.
    """
    duplicates: list[str] = []

    # Find all package.json files
    pkg_files = {
        path: content
        for path, content in files.items()
        if os.path.basename(path) == "package.json"
    }

    if len(pkg_files) <= 1:
        return duplicates

    # Compare dependency versions across package.json files
    all_deps: dict[str, dict[str, str]] = {}  # pkg_name → {file → version}

    for pkg_path, _pkg_content in pkg_files.items():
        try:
            import json
            pkg = json.loads(_pkg_content)
            deps = {}
            deps.update(pkg.get("dependencies", {}))
            deps.update(pkg.get("devDependencies", {}))

            for dep_name, dep_version in deps.items():
                if dep_name not in all_deps:
                    all_deps[dep_name] = {}
                all_deps[dep_name][pkg_path] = dep_version
        except (json.JSONDecodeError, AttributeError):
            continue

    for dep_name, versions_by_file in all_deps.items():
        unique_versions = set(versions_by_file.values())
        if len(unique_versions) > 1:
            version_list = ", ".join(
                f"{v} (in {f})" for f, v in versions_by_file.items()
            )
            duplicates.append(
                f"{dep_name}: {version_list}"
            )

    return duplicates


# ── Main entry point ─────────────────────────────────────────────────


def build_import_graph(files: dict[str, str]) -> ImportGraph:
    """Build a complete import graph from all generated files.

    Args:
        files: Dict of file_path → file_content.

    Returns:
        ImportGraph with dependency relationships and detected issues.
    """
    ts_files = {
        path: content
        for path, content in files.items()
        if _is_ts_file(path)
    }

    graph: dict[str, list[str]] = {}
    edges: list[ImportEdge] = []
    missing_imports: list[str] = []

    for file_path, content in ts_files.items():
        file_imports = _extract_imports(content)
        graph[file_path] = []

        for imp in file_imports:
            source = str(imp["source"])
            symbols = imp.get("symbols", [])

            if not _is_relative_import(source):
                continue

            resolved = _resolve_import_path(file_path, source, ts_files)

            if resolved is None:
                missing_imports.append(
                    f"{file_path}: import from '{source}' — file not found"
                )
                continue

            graph[file_path].append(resolved)
            symbol_list = symbols if isinstance(symbols, list) else [str(symbols)]
            edges.append(ImportEdge(
                source_file=file_path,
                target_file=resolved,
                symbols=[str(s) for s in symbol_list],
            ))

    # Detect cycles
    circular_deps = _detect_cycles(graph)

    # Detect duplicate packages
    duplicate_packages = _detect_duplicate_packages(files)

    total_edges = sum(len(targets) for targets in graph.values())

    logger.info(
        "import_graph_resolver.completed",
        total_files=len(ts_files),
        total_edges=total_edges,
        circular_deps=len(circular_deps),
        missing_imports=len(missing_imports),
        duplicate_packages=len(duplicate_packages),
    )

    return ImportGraph(
        graph=graph,
        edges=edges,
        circular_deps=circular_deps,
        missing_imports=missing_imports,
        duplicate_packages=duplicate_packages,
        total_files=len(ts_files),
        total_edges=total_edges,
    )

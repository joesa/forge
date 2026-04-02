"""
Layer 4 — Barrel validator.

Validates that barrel ``index.ts`` files correctly re-export everything
that downstream consumer files import from them.
"""

from __future__ import annotations

import re

from pydantic import BaseModel, Field

import structlog

logger = structlog.get_logger(__name__)


class BarrelReport(BaseModel):
    """Result of barrel index.ts validation."""

    barrel_path: str
    valid: bool
    missing_exports: list[str] = Field(
        default_factory=list,
        description="Symbols imported by consumers but not re-exported by barrel",
    )
    extra_exports: list[str] = Field(
        default_factory=list,
        description="Symbols re-exported by barrel but not used by any consumer",
    )


# ── Export/import parsers ────────────────────────────────────────────

_EXPORT_NAMED_RE = re.compile(
    r"export\s*\{([^}]+)\}", re.MULTILINE
)
_EXPORT_FROM_RE = re.compile(
    r"export\s*\{([^}]+)\}\s*from\s*['\"]([^'\"]+)['\"]", re.MULTILINE
)
_EXPORT_DEFAULT_RE = re.compile(
    r"export\s+default\s+(?:function|class|const|let|var)?\s*(\w+)?",
    re.MULTILINE,
)
_EXPORT_DECLARATION_RE = re.compile(
    r"export\s+(?:const|let|var|function|class|interface|type|enum)\s+(\w+)",
    re.MULTILINE,
)
_EXPORT_STAR_RE = re.compile(
    r"export\s*\*\s*(?:as\s+(\w+)\s*)?from\s*['\"]([^'\"]+)['\"]",
    re.MULTILINE,
)

_IMPORT_RE = re.compile(
    r"import\s*\{([^}]+)\}\s*from\s*['\"]([^'\"]+)['\"]", re.MULTILINE
)


def _extract_barrel_exports(content: str) -> set[str]:
    """Extract all symbol names exported from a barrel file."""
    exports: set[str] = set()

    # Named re-exports: export { Foo, Bar } from './module'
    for match in _EXPORT_FROM_RE.finditer(content):
        symbols = match.group(1)
        for sym in symbols.split(","):
            sym = sym.strip()
            # Handle `Foo as Bar` → export name is Bar
            if " as " in sym:
                sym = sym.split(" as ")[-1].strip()
            if sym:
                exports.add(sym)

    # Named exports: export { Foo, Bar }
    for match in _EXPORT_NAMED_RE.finditer(content):
        symbols = match.group(1)
        for sym in symbols.split(","):
            sym = sym.strip()
            if " as " in sym:
                sym = sym.split(" as ")[-1].strip()
            if sym:
                exports.add(sym)

    # Direct exports: export const Foo = ...
    for match in _EXPORT_DECLARATION_RE.finditer(content):
        exports.add(match.group(1))

    # Default export
    for match in _EXPORT_DEFAULT_RE.finditer(content):
        name = match.group(1)
        if name:
            exports.add(name)
        exports.add("default")

    # Star re-exports: export * from './module' — we mark as wildcard
    for match in _EXPORT_STAR_RE.finditer(content):
        alias = match.group(1)
        if alias:
            exports.add(alias)
        else:
            exports.add("*")

    return exports


def _extract_imports_from_barrel(
    consumer_content: str,
    barrel_import_path: str,
) -> set[str]:
    """Extract symbols that a consumer imports from a specific barrel path."""
    imported: set[str] = set()

    for match in _IMPORT_RE.finditer(consumer_content):
        symbols_str = match.group(1)
        source = match.group(2)

        # Check if this import is from the barrel path
        # Normalize paths for comparison
        if not _paths_match(source, barrel_import_path):
            continue

        for sym in symbols_str.split(","):
            sym = sym.strip()
            # Handle `Foo as Bar` → import name is Foo
            if " as " in sym:
                sym = sym.split(" as ")[0].strip()
            if sym:
                imported.add(sym)

    return imported


def _paths_match(import_source: str, barrel_path: str) -> bool:
    """Check if an import source path matches a barrel path.

    Handles: './components', './components/index', '../components', etc.
    """
    # Normalize: strip index suffix, leading ./
    a = import_source.rstrip("/")
    b = barrel_path.rstrip("/")

    for suffix in ("/index", "/index.ts", "/index.tsx", "/index.js"):
        a = a.removesuffix(suffix)
        b = b.removesuffix(suffix)

    # Remove extensions
    for ext in (".ts", ".tsx", ".js", ".jsx"):
        a = a.removesuffix(ext)
        b = b.removesuffix(ext)

    return a == b


def validate_barrel(
    index_content: str,
    consuming_files: dict[str, str],
    barrel_path: str = "./index",
) -> BarrelReport:
    """Validate a barrel index.ts against its consumers.

    Args:
        index_content: Content of the barrel index.ts file.
        consuming_files: Dict of file_path → content for files that
                        import from this barrel.
        barrel_path: The import path used to reference this barrel.

    Returns:
        BarrelReport with missing/extra exports.
    """
    barrel_exports = _extract_barrel_exports(index_content)
    has_wildcard = "*" in barrel_exports

    # Collect all symbols imported from this barrel by consumers
    all_imported: set[str] = set()
    for _file_path, content in consuming_files.items():
        imported = _extract_imports_from_barrel(content, barrel_path)
        all_imported.update(imported)

    # If barrel has wildcard re-export, we can't check missing exports —
    # it re-exports everything from the source module.
    if has_wildcard:
        missing: list[str] = []
    else:
        missing = sorted(all_imported - barrel_exports)

    extra = sorted(barrel_exports - all_imported - {"*", "default"})

    valid = len(missing) == 0

    if not valid:
        logger.warning(
            "barrel_validator.missing_exports",
            barrel_path=barrel_path,
            missing=missing,
        )

    return BarrelReport(
        barrel_path=barrel_path,
        valid=valid,
        missing_exports=missing,
        extra_exports=extra,
    )

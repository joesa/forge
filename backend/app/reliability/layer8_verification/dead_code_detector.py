"""
Layer 8 — Dead code detector via ts-prune.

Identifies unused exports (exported but never imported) and unused
imports (imported but never used) in TypeScript/JavaScript codebases.

This tool is NON-BLOCKING — it reports warnings but never fails the
build.  Results are logged for developer review.
"""

from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass, field
from pathlib import Path

import structlog

logger = structlog.get_logger(__name__)


# ── Report types ────────────────────────────────────────────────────


@dataclass
class UnusedExport:
    """An export that is never imported anywhere."""

    file_path: str
    export_name: str
    line_number: int = 0


@dataclass
class UnusedImport:
    """An import that is never used in the importing file."""

    file_path: str
    import_name: str
    from_module: str = ""
    line_number: int = 0


@dataclass
class DeadCodeReport:
    """Dead code detection report."""

    unused_exports: list[UnusedExport] = field(default_factory=list)
    unused_imports: list[UnusedImport] = field(default_factory=list)
    files_checked: int = 0
    error: str | None = None


# ── ts-prune integration ────────────────────────────────────────────


async def _run_ts_prune(project_dir: str) -> list[UnusedExport]:
    """
    Run ts-prune on a TypeScript project directory.

    Returns a list of unused exports if ts-prune is available.
    Falls back to built-in analysis otherwise.
    """
    unused: list[UnusedExport] = []

    try:
        cmd = f"npx ts-prune --project {project_dir}/tsconfig.json 2>/dev/null"

        process = await asyncio.create_subprocess_shell(
            cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=project_dir,
        )
        stdout, _stderr = await asyncio.wait_for(
            process.communicate(), timeout=60
        )

        if stdout:
            for line in stdout.decode().strip().split("\n"):
                if not line.strip():
                    continue
                # ts-prune output format: "path/to/file.ts:42 - exportName"
                match = re.match(
                    r"^(.+?):(\d+)\s*-\s*(.+?)(?:\s+\(used in module\))?$",
                    line.strip(),
                )
                if match:
                    file_path = match.group(1)
                    line_num = int(match.group(2))
                    export_name = match.group(3).strip()

                    # Skip "(used in module)" entries — those are used
                    if "(used in module)" in line:
                        continue

                    unused.append(UnusedExport(
                        file_path=file_path,
                        export_name=export_name,
                        line_number=line_num,
                    ))

    except FileNotFoundError:
        logger.info(
            "ts_prune_not_installed",
            msg="Falling back to built-in analysis",
        )
    except asyncio.TimeoutError:
        logger.warning("ts_prune_timeout")
    except Exception as exc:
        logger.warning("ts_prune_error", error=str(exc))

    return unused


# ── Built-in analysis ──────────────────────────────────────────────


def _find_exports(
    file_path: str,
    content: str,
) -> list[tuple[str, int]]:
    """Find all named exports in a TypeScript/JavaScript file."""
    exports: list[tuple[str, int]] = []

    # export const/let/var/function/class/type/interface/enum
    export_pattern = re.compile(
        r"^export\s+(?:const|let|var|function|class|type|interface|enum|async\s+function)\s+"
        r"([A-Za-z_$][A-Za-z0-9_$]*)",
        re.MULTILINE,
    )
    for match in export_pattern.finditer(content):
        line_num = content[: match.start()].count("\n") + 1
        exports.append((match.group(1), line_num))

    # export { name1, name2 }
    export_list_pattern = re.compile(
        r"export\s*\{([^}]+)\}", re.MULTILINE
    )
    for match in export_list_pattern.finditer(content):
        names = match.group(1)
        line_num = content[: match.start()].count("\n") + 1
        for name in names.split(","):
            name = name.strip().split(" as ")[0].strip()
            if name:
                exports.append((name, line_num))

    # export default — track as "default"
    default_pattern = re.compile(
        r"^export\s+default\s+(?:function|class|const)?\s*"
        r"([A-Za-z_$][A-Za-z0-9_$]*)?",
        re.MULTILINE,
    )
    for match in default_pattern.finditer(content):
        line_num = content[: match.start()].count("\n") + 1
        name = match.group(1) or "default"
        exports.append((name, line_num))

    return exports


def _find_imports(
    file_path: str,
    content: str,
) -> list[tuple[str, str, int]]:
    """
    Find all imports in a TypeScript/JavaScript file.

    Returns list of (import_name, from_module, line_number).
    """
    imports: list[tuple[str, str, int]] = []

    # import { name1, name2 } from 'module'
    named_import = re.compile(
        r"import\s*\{([^}]+)\}\s*from\s*['\"]([^'\"]+)['\"]",
        re.MULTILINE,
    )
    for match in named_import.finditer(content):
        names = match.group(1)
        module = match.group(2)
        line_num = content[: match.start()].count("\n") + 1
        for name in names.split(","):
            name = name.strip()
            # Handle `name as alias`
            parts = name.split(" as ")
            actual_name = parts[-1].strip() if len(parts) > 1 else parts[0].strip()
            if actual_name:
                imports.append((actual_name, module, line_num))

    # import name from 'module'
    default_import = re.compile(
        r"import\s+([A-Za-z_$][A-Za-z0-9_$]*)\s+from\s*['\"]([^'\"]+)['\"]",
        re.MULTILINE,
    )
    for match in default_import.finditer(content):
        name = match.group(1)
        module = match.group(2)
        line_num = content[: match.start()].count("\n") + 1
        imports.append((name, module, line_num))

    # import * as name from 'module'
    star_import = re.compile(
        r"import\s*\*\s*as\s+([A-Za-z_$][A-Za-z0-9_$]*)\s+from\s*['\"]([^'\"]+)['\"]",
        re.MULTILINE,
    )
    for match in star_import.finditer(content):
        name = match.group(1)
        module = match.group(2)
        line_num = content[: match.start()].count("\n") + 1
        imports.append((name, module, line_num))

    return imports


def _is_name_used(name: str, content: str, import_line: int) -> bool:
    """
    Check if an imported name is actually used in the file content
    (beyond the import statement itself).
    """
    lines = content.split("\n")
    usage_count = 0

    # Simple heuristic: check if the name appears outside import lines
    # as a word boundary match
    pattern = re.compile(rf"\b{re.escape(name)}\b")

    for i, line in enumerate(lines, 1):
        if i == import_line:
            continue
        # Skip other import lines
        stripped = line.strip()
        if stripped.startswith("import "):
            continue
        if pattern.search(line):
            usage_count += 1

    return usage_count > 0


# ── Public API ──────────────────────────────────────────────────────


async def detect_dead_code(
    generated_files: dict[str, str],
) -> DeadCodeReport:
    """
    Detect dead code (unused exports and imports) in generated files.

    Parameters
    ----------
    generated_files : dict[str, str]
        Mapping of file paths to file contents.

    Returns
    -------
    DeadCodeReport
        Report with unused exports and imports.
        This is a WARNING ONLY tool — it never fails the build.
    """
    report = DeadCodeReport()

    if not generated_files:
        report.error = "No files provided"
        return report

    try:
        # Filter to JS/TS files
        ts_js_extensions = {".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs"}

        ts_js_files: dict[str, str] = {}
        for file_path, content in generated_files.items():
            ext = Path(file_path).suffix.lower()
            if ext in ts_js_extensions:
                ts_js_files[file_path] = content

        report.files_checked = len(ts_js_files)

        if not ts_js_files:
            logger.info("dead_code_no_ts_files", msg="No TS/JS files to analyse")
            return report

        # Collect all exports and all imports across the project
        all_exports: dict[str, list[tuple[str, int]]] = {}
        all_imports: dict[str, list[tuple[str, str, int]]] = {}
        all_imported_names: set[str] = set()

        for file_path, content in ts_js_files.items():
            exports = _find_exports(file_path, content)
            imports = _find_imports(file_path, content)
            all_exports[file_path] = exports
            all_imports[file_path] = imports

            for imp_name, _module, _line in imports:
                all_imported_names.add(imp_name)

        # Find unused exports (exported but never imported anywhere)
        for file_path, exports in all_exports.items():
            for export_name, line_num in exports:
                # Skip common patterns that are expected to be entry points
                if export_name in (
                    "default", "App", "main", "index",
                    "handler", "middleware",
                ):
                    continue

                # Check if this export is imported anywhere
                if export_name not in all_imported_names:
                    report.unused_exports.append(UnusedExport(
                        file_path=file_path,
                        export_name=export_name,
                        line_number=line_num,
                    ))

        # Find unused imports (imported but never used in that file)
        for file_path, imports in all_imports.items():
            content = ts_js_files[file_path]
            for imp_name, from_module, line_num in imports:
                if not _is_name_used(imp_name, content, line_num):
                    report.unused_imports.append(UnusedImport(
                        file_path=file_path,
                        import_name=imp_name,
                        from_module=from_module,
                        line_number=line_num,
                    ))

        logger.info(
            "dead_code_detection_complete",
            files_checked=report.files_checked,
            unused_exports=len(report.unused_exports),
            unused_imports=len(report.unused_imports),
        )

    except Exception as exc:
        report.error = str(exc)
        logger.error("dead_code_detection_failed", error=str(exc))

    return report

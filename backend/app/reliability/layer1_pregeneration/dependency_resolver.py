"""
Layer 1 — Dependency resolver.

Resolves npm peer-dependency compatibility for each package in a tech stack,
auto-resolves version conflicts to highest compatible version, and returns
a deterministic result.
"""

from __future__ import annotations

import hashlib
import json
import re

from pydantic import BaseModel, Field

import structlog

logger = structlog.get_logger(__name__)


# ── Pydantic models ──────────────────────────────────────────────────


class ResolvedDependencies(BaseModel):
    """Result of dependency resolution."""

    packages: dict[str, str] = Field(
        description="Package name → pinned version"
    )
    lockfile_hash: str = Field(
        description="SHA-256 hash of resolved dependency set"
    )
    conflicts_resolved: int = Field(
        default=0, ge=0,
        description="Number of version conflicts auto-resolved"
    )
    unresolved_conflicts: list[str] = Field(
        default_factory=list,
        description="Conflicts that could not be auto-resolved"
    )


# ── Built-in compatibility matrix ────────────────────────────────────
# Maps package name → {version, peer_deps: {pkg: version_range}}

_PACKAGE_REGISTRY: dict[str, dict[str, object]] = {
    # React ecosystem
    "react": {
        "version": "18.3.1",
        "peer_deps": {},
    },
    "react-dom": {
        "version": "18.3.1",
        "peer_deps": {"react": "^18.0.0"},
    },
    "react-router-dom": {
        "version": "6.28.0",
        "peer_deps": {"react": ">=16.8", "react-dom": ">=16.8"},
    },
    # Next.js
    "next": {
        "version": "14.2.20",
        "peer_deps": {"react": "^18.2.0", "react-dom": "^18.2.0"},
    },
    # Vite
    "vite": {
        "version": "5.4.14",
        "peer_deps": {},
    },
    "@vitejs/plugin-react": {
        "version": "4.3.4",
        "peer_deps": {"vite": "^4.2.0 || ^5.0.0"},
    },
    # Tailwind CSS
    "tailwindcss": {
        "version": "3.4.17",
        "peer_deps": {},
    },
    "autoprefixer": {
        "version": "10.4.20",
        "peer_deps": {},
    },
    "postcss": {
        "version": "8.4.49",
        "peer_deps": {},
    },
    # State management
    "zustand": {
        "version": "4.5.5",
        "peer_deps": {"react": ">=16.8"},
    },
    "@tanstack/react-query": {
        "version": "5.62.7",
        "peer_deps": {"react": "^18.0.0"},
    },
    # UI
    "framer-motion": {
        "version": "11.15.0",
        "peer_deps": {"react": "^18.0.0", "react-dom": "^18.0.0"},
    },
    # Forms
    "react-hook-form": {
        "version": "7.54.2",
        "peer_deps": {"react": "^16.8.0 || ^17 || ^18"},
    },
    "zod": {
        "version": "3.24.1",
        "peer_deps": {},
    },
    "@hookform/resolvers": {
        "version": "3.9.1",
        "peer_deps": {"react-hook-form": "^7.0.0"},
    },
    # Editor
    "@monaco-editor/react": {
        "version": "4.6.0",
        "peer_deps": {"react": "^16.8.0 || ^17 || ^18", "react-dom": "^16.8.0 || ^17 || ^18"},
    },
    # Terminal
    "xterm": {
        "version": "5.5.0",
        "peer_deps": {},
    },
    # HTTP
    "axios": {
        "version": "1.7.9",
        "peer_deps": {},
    },
    # TypeScript
    "typescript": {
        "version": "5.4.5",
        "peer_deps": {},
    },
}

# ── Framework presets ─────────────────────────────────────────────────

_FRAMEWORK_PRESETS: dict[str, list[str]] = {
    "react_vite": [
        "react", "react-dom", "vite", "@vitejs/plugin-react",
        "typescript", "tailwindcss", "postcss", "autoprefixer",
    ],
    "nextjs": [
        "react", "react-dom", "next",
        "typescript", "tailwindcss", "postcss", "autoprefixer",
    ],
    "remix": [
        "react", "react-dom",
        "typescript", "tailwindcss", "postcss", "autoprefixer",
    ],
}


# ── Semver helpers ───────────────────────────────────────────────────

_SEMVER_RE = re.compile(r"(\d+)\.(\d+)\.(\d+)")
_SEMVER_PARTIAL_RE = re.compile(r"(\d+)(?:\.(\d+))?(?:\.(\d+))?")


def _parse_version(version: str) -> tuple[int, int, int] | None:
    """Parse a semver string into (major, minor, patch).

    Handles full (18.3.1), partial (16.8), and major-only (18) versions.
    """
    m = _SEMVER_RE.search(version)
    if m:
        return int(m.group(1)), int(m.group(2)), int(m.group(3))
    # Try partial version (e.g., "16.8" or "18")
    m = _SEMVER_PARTIAL_RE.search(version)
    if m:
        major = int(m.group(1))
        minor = int(m.group(2)) if m.group(2) else 0
        patch = int(m.group(3)) if m.group(3) else 0
        return major, minor, patch
    return None


def _satisfies_range(version: str, range_str: str) -> bool:
    """Check if a version satisfies a semver range.

    Supports: ^x.y.z, >=x.y.z, ~x.y.z, x.y.z, and || for alternatives.
    """
    parsed = _parse_version(version)
    if parsed is None:
        return False

    # Handle || (or) ranges
    if "||" in range_str:
        parts = [p.strip() for p in range_str.split("||")]
        return any(_satisfies_range(version, part) for part in parts)

    range_str = range_str.strip()

    # Exact match
    range_parsed = _parse_version(range_str)
    if range_parsed and not any(
        range_str.startswith(c) for c in ("^", "~", ">=", ">", "<=", "<")
    ):
        return parsed == range_parsed

    # ^x.y.z — compatible with major version
    if range_str.startswith("^"):
        range_parsed = _parse_version(range_str[1:])
        if range_parsed is None:
            return False
        if range_parsed[0] == 0:
            # ^0.x.y means >=0.x.y <0.(x+1).0
            return parsed[0] == 0 and parsed[1] == range_parsed[1] and parsed >= range_parsed
        return parsed[0] == range_parsed[0] and parsed >= range_parsed

    # >=x.y.z
    if range_str.startswith(">="):
        range_parsed = _parse_version(range_str[2:])
        if range_parsed is None:
            return False
        return parsed >= range_parsed

    # ~x.y.z — compatible with minor version
    if range_str.startswith("~"):
        range_parsed = _parse_version(range_str[1:])
        if range_parsed is None:
            return False
        return (
            parsed[0] == range_parsed[0]
            and parsed[1] == range_parsed[1]
            and parsed >= range_parsed
        )

    # Fallback: try exact match with cleaned string
    range_parsed = _parse_version(range_str)
    if range_parsed:
        return parsed >= range_parsed
    return True  # Unknown range format — permissive


# ── Main resolver ────────────────────────────────────────────────────


def resolve_dependencies(tech_stack: list[str]) -> ResolvedDependencies:
    """Resolve npm dependencies for a given tech stack.

    Args:
        tech_stack: List of package names and/or framework presets
                   (e.g. ["react_vite", "zustand", "@tanstack/react-query"])

    Returns:
        ResolvedDependencies with pinned versions, lockfile hash, and
        conflict resolution info.
    """
    # Expand framework presets
    requested: list[str] = []
    for item in tech_stack:
        if item in _FRAMEWORK_PRESETS:
            requested.extend(_FRAMEWORK_PRESETS[item])
        else:
            requested.append(item)

    # Deduplicate while preserving order
    seen: set[str] = set()
    unique_requested: list[str] = []
    for pkg in requested:
        if pkg not in seen:
            seen.add(pkg)
            unique_requested.append(pkg)

    packages: dict[str, str] = {}
    conflicts_resolved = 0
    unresolved: list[str] = []

    # Phase 1: Resolve direct dependencies
    for pkg_name in unique_requested:
        entry = _PACKAGE_REGISTRY.get(pkg_name)
        if entry:
            packages[pkg_name] = str(entry["version"])
        else:
            # Unknown package — use latest placeholder
            packages[pkg_name] = "latest"
            logger.warning(
                "dependency_resolver.unknown_package",
                package=pkg_name,
            )

    # Phase 2: Check peer dependency compatibility
    for pkg_name in list(packages.keys()):
        entry = _PACKAGE_REGISTRY.get(pkg_name)
        if not entry:
            continue

        peer_deps = entry.get("peer_deps", {})
        if not isinstance(peer_deps, dict):
            continue

        for peer_name, peer_range in peer_deps.items():
            if not isinstance(peer_range, str):
                continue

            if peer_name not in packages:
                # Auto-add missing peer dependency
                peer_entry = _PACKAGE_REGISTRY.get(peer_name)
                if peer_entry:
                    packages[peer_name] = str(peer_entry["version"])
                    conflicts_resolved += 1
                    logger.info(
                        "dependency_resolver.auto_added_peer",
                        package=pkg_name,
                        peer=peer_name,
                        version=peer_entry["version"],
                    )
                else:
                    unresolved.append(
                        f"{pkg_name} requires peer {peer_name} ({peer_range}) "
                        f"but it is unknown"
                    )
                continue

            # Validate version compatibility
            current_version = packages[peer_name]
            if current_version == "latest":
                continue

            if not _satisfies_range(current_version, peer_range):
                # Try to find a compatible version from registry
                peer_entry = _PACKAGE_REGISTRY.get(peer_name)
                if peer_entry:
                    candidate = str(peer_entry["version"])
                    if _satisfies_range(candidate, peer_range):
                        packages[peer_name] = candidate
                        conflicts_resolved += 1
                        logger.info(
                            "dependency_resolver.conflict_resolved",
                            package=pkg_name,
                            peer=peer_name,
                            old_version=current_version,
                            new_version=candidate,
                        )
                    else:
                        unresolved.append(
                            f"{pkg_name} requires {peer_name}@{peer_range} "
                            f"but resolved to {current_version}"
                        )
                else:
                    unresolved.append(
                        f"{pkg_name} requires {peer_name}@{peer_range} "
                        f"but {peer_name} is unknown"
                    )

    # Generate deterministic lockfile hash
    sorted_pkgs = json.dumps(
        dict(sorted(packages.items())), sort_keys=True
    )
    lockfile_hash = hashlib.sha256(sorted_pkgs.encode()).hexdigest()

    return ResolvedDependencies(
        packages=dict(sorted(packages.items())),
        lockfile_hash=lockfile_hash,
        conflicts_resolved=conflicts_resolved,
        unresolved_conflicts=unresolved,
    )

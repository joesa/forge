"""
Layer 6 — Incremental build detection.

Detects which files differ between a new build and a cached build
using SHA-256 hash comparison.  Enables rebuilding only changed
modules on re-run builds.
"""

from __future__ import annotations

import hashlib

import structlog

logger = structlog.get_logger(__name__)


def _hash_content(content: str) -> str:
    """Compute SHA-256 hash of file content."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def detect_changed_modules(
    new_files: dict[str, str],
    cached_files: dict[str, str],
) -> list[str]:
    """Detect which files differ between new and cached builds.

    Compares file contents by SHA-256 hash.  Returns paths of files
    that are new, modified, or deleted.

    Args:
        new_files: Dict of file_path → file_content from new build.
        cached_files: Dict of file_path → file_content from cache.

    Returns:
        List of changed file paths (new, modified, or deleted).
    """
    changed: list[str] = []

    # Hash all cached files
    cached_hashes: dict[str, str] = {
        path: _hash_content(content)
        for path, content in cached_files.items()
    }

    # Hash all new files
    new_hashes: dict[str, str] = {
        path: _hash_content(content)
        for path, content in new_files.items()
    }

    # Find new or modified files
    for path, new_hash in new_hashes.items():
        cached_hash = cached_hashes.get(path)
        if cached_hash is None:
            # New file
            changed.append(path)
        elif cached_hash != new_hash:
            # Modified file
            changed.append(path)

    # Find deleted files
    for path in cached_hashes:
        if path not in new_hashes:
            changed.append(path)

    # Sort for deterministic output
    changed.sort()

    logger.info(
        "incremental_build.detected",
        new_files=len(new_files),
        cached_files=len(cached_files),
        changed_count=len(changed),
        new_count=sum(
            1 for p in changed if p not in cached_hashes
        ),
        modified_count=sum(
            1 for p in changed
            if p in cached_hashes and p in new_hashes
        ),
        deleted_count=sum(
            1 for p in changed if p not in new_hashes
        ),
    )

    return changed

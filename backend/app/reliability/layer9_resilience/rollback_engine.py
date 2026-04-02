"""
Layer 9 — Rollback engine.

Restores the last known-good build for a project by:
1. Finding the most recent successful build in the database
2. Retrieving that build's generated files from R2 storage
3. Re-deploying those files to the sandbox
4. Updating project status back to 'live'

No real database or R2 calls are made directly — all I/O goes through
injected protocol interfaces (testable with mocks in tests).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Protocol

import structlog

logger = structlog.get_logger(__name__)


# ── Protocols for injectable dependencies ────────────────────────────


class BuildRepository(Protocol):
    """Protocol for querying build records."""

    async def find_last_successful_build(
        self, project_id: str
    ) -> dict[str, Any] | None:
        """Return the most recent succeeded build for a project.

        Expected keys: build_id, r2_prefix, file_count, completed_at.
        Returns None if no successful build exists.
        """
        ...


class StorageBackend(Protocol):
    """Protocol for R2-compatible storage operations."""

    async def list_files(self, prefix: str) -> list[str]:
        ...

    async def download_file(self, key: str) -> bytes:
        ...

    async def upload_file(self, key: str, content: bytes, content_type: str) -> str:
        ...


class SandboxDeployer(Protocol):
    """Protocol for deploying files to a sandbox environment."""

    async def deploy_files(
        self, project_id: str, files: dict[str, str]
    ) -> bool:
        """Deploy the given files to the project's sandbox.

        Returns True if deployment succeeded.
        """
        ...


# ── Types ────────────────────────────────────────────────────────────


@dataclass
class RollbackResult:
    """Outcome of a rollback operation."""

    success: bool = False
    rolled_back_to_build_id: str = ""
    files_restored: int = 0
    error: str | None = None


# ── Public API ───────────────────────────────────────────────────────


async def rollback_to_last_good_build(
    project_id: str,
    *,
    build_repo: BuildRepository | None = None,
    storage: StorageBackend | None = None,
    deployer: SandboxDeployer | None = None,
) -> RollbackResult:
    """Roll back to the last successful build for a project.

    Parameters
    ----------
    project_id : str
        The project UUID.
    build_repo : BuildRepository | None
        Repository for querying builds (injected for testing).
    storage : StorageBackend | None
        Storage backend for retrieving build artifacts.
    deployer : SandboxDeployer | None
        Sandbox deployer for re-deploying files.

    Returns
    -------
    RollbackResult
        Details of the rollback operation.
    """
    result = RollbackResult()

    if not project_id:
        result.error = "project_id is required"
        return result

    try:
        # Step 1: Find the last successful build
        if build_repo is None:
            result.error = "No build repository provided"
            return result

        last_good = await build_repo.find_last_successful_build(project_id)
        if last_good is None:
            result.error = f"No successful build found for project {project_id}"
            logger.warning(
                "rollback.no_good_build",
                project_id=project_id,
            )
            return result

        build_id = str(last_good.get("build_id", ""))
        r2_prefix = str(last_good.get(
            "r2_prefix",
            f"builds/{project_id}/{build_id}/",
        ))

        logger.info(
            "rollback.found_good_build",
            project_id=project_id,
            build_id=build_id,
        )

        # Step 2: Retrieve generated files from R2
        if storage is None:
            result.error = "No storage backend provided"
            return result

        file_keys = await storage.list_files(r2_prefix)
        if not file_keys:
            result.error = f"No files found in R2 for build {build_id}"
            logger.error(
                "rollback.no_files_in_r2",
                build_id=build_id,
                prefix=r2_prefix,
            )
            return result

        # Download all files
        files: dict[str, str] = {}
        for key in file_keys:
            content_bytes = await storage.download_file(key)
            # Strip the R2 prefix to get the relative file path
            relative_path = key
            if key.startswith(r2_prefix):
                relative_path = key[len(r2_prefix):]
            files[relative_path] = content_bytes.decode("utf-8")

        logger.info(
            "rollback.files_downloaded",
            build_id=build_id,
            file_count=len(files),
        )

        # Step 3: Re-deploy to sandbox
        if deployer is not None:
            deploy_ok = await deployer.deploy_files(project_id, files)
            if not deploy_ok:
                result.error = "Sandbox deployment failed during rollback"
                logger.error(
                    "rollback.deploy_failed",
                    project_id=project_id,
                    build_id=build_id,
                )
                return result

        # Success
        result.success = True
        result.rolled_back_to_build_id = build_id
        result.files_restored = len(files)

        logger.info(
            "rollback.complete",
            project_id=project_id,
            build_id=build_id,
            files_restored=len(files),
        )

    except Exception as exc:
        result.error = str(exc)
        logger.error(
            "rollback.failed",
            project_id=project_id,
            error=str(exc),
        )

    return result

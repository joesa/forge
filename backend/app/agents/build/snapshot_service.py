"""
Snapshot Service — captures build state after each agent completes.

After every build agent finishes, the pipeline calls
``capture_snapshot()`` to serialize the current generated_files
file tree and upload it to Cloudflare R2 for timeline replay.

Each build has up to 10 snapshots (one per agent).
"""

from __future__ import annotations

import json
import time
from typing import Any

import structlog

from app.services.storage_service import upload_file

logger = structlog.get_logger(__name__)


class SnapshotService:
    """Captures and uploads build-state snapshots to R2."""

    async def capture_snapshot(
        self,
        build_id: str,
        project_id: str,
        agent_name: str,
        snapshot_index: int,
        generated_files: dict[str, str] | None = None,
        gate_results: dict[str, Any] | None = None,
    ) -> str:
        """Capture a snapshot of the current build state.

        Parameters
        ----------
        build_id : str
            Unique build identifier.
        project_id : str
            Project this build belongs to.
        agent_name : str
            Name of the agent that just completed.
        snapshot_index : int
            Sequential index (1-10) for ordering snapshots.
        generated_files : dict[str, str] | None
            Current file tree: path → content.
        gate_results : dict[str, Any] | None
            Current gate results at time of snapshot.

        Returns
        -------
        str
            R2 object key where the snapshot was stored.
        """
        snapshot_data: dict[str, Any] = {
            "build_id": build_id,
            "project_id": project_id,
            "agent_name": agent_name,
            "snapshot_index": snapshot_index,
            "timestamp": time.time(),
            "file_count": len(generated_files) if generated_files else 0,
            "file_tree": (
                list(generated_files.keys()) if generated_files else []
            ),
            "gate_results": gate_results or {},
        }

        # R2 key: builds/{build_id}/snapshots/{index}_{agent_name}.json
        r2_key = (
            f"builds/{build_id}/snapshots/"
            f"{snapshot_index:02d}_{agent_name}.json"
        )

        try:
            content = json.dumps(snapshot_data, indent=2).encode("utf-8")
            await upload_file(
                key=r2_key,
                content=content,
                content_type="application/json",
            )
            logger.info(
                "snapshot_service.captured",
                build_id=build_id,
                agent=agent_name,
                index=snapshot_index,
                r2_key=r2_key,
                file_count=snapshot_data["file_count"],
            )
            return r2_key
        except Exception as exc:
            # Snapshot failure should not block the build pipeline
            logger.error(
                "snapshot_service.capture_failed",
                build_id=build_id,
                agent=agent_name,
                index=snapshot_index,
                error=str(exc),
            )
            return ""

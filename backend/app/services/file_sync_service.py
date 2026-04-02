"""
File sync service — real-time file synchronization to sandboxes.

Publishes file changes to Redis. The sandbox runs a file sync daemon
subscribed to the channel that writes the file, which triggers
Vite/Next dev server HMR.

Target: < 700ms from this call to browser update.
"""

import time

import structlog

from app.core.redis import publish_event

logger = structlog.get_logger(__name__)


async def sync_file(
    sandbox_id: str,
    file_path: str,
    content: str,
) -> bool:
    """
    Publish a file change to the sandbox's sync channel.

    The sandbox's file sync daemon subscribes to "file_sync:{sandbox_id}"
    and writes the file to disk. The Vite/Next dev server picks up the
    change via its HMR watcher.

    Returns True if published successfully.
    """
    channel = f"file_sync:{sandbox_id}"
    timestamp_ms = int(time.time() * 1000)

    payload = {
        "path": file_path,
        "content": content,
        "timestamp": timestamp_ms,
    }

    try:
        await publish_event(channel, payload)
        logger.info(
            "file_sync_published",
            sandbox_id=sandbox_id,
            file_path=file_path,
            content_length=len(content),
            timestamp_ms=timestamp_ms,
        )
        return True
    except Exception as exc:
        logger.error(
            "file_sync_publish_failed",
            sandbox_id=sandbox_id,
            file_path=file_path,
            error=str(exc),
        )
        raise

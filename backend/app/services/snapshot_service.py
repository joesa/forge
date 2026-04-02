"""
Snapshot service — build timeline snapshots.

Captures screenshots at each build agent stage for timeline replay.
Each snapshot: Playwright → WebP → R2 → DB record → Redis event.
"""

import datetime
import time
import uuid

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.project import Project

from app.config import settings
from app.core.redis import publish_event
from app.models.build import Build, BuildStatus
from app.models.build_snapshot import BuildSnapshot
from app.schemas.preview import SnapshotResponse
from app.services import storage_service

logger = structlog.get_logger(__name__)


async def capture_snapshot(
    build_id: str,
    project_id: str,
    agent_type: str,
    agent_number: int,
    session: AsyncSession,
) -> BuildSnapshot:
    """
    Capture a snapshot of the preview at the current build stage.

    Steps:
      1. Playwright → navigate to preview URL "/"
      2. Wait for React hydration (#root children, 5s timeout)
      3. Full-page screenshot → WebP → R2
      4. Create build_snapshots record
      5. PUBLISH Redis event for real-time UI updates

    R2 key: snapshots/{project_id}/{build_id}/{agent_number:02d}_{agent_type}.webp
    """
    from playwright.async_api import async_playwright

    timestamp = int(time.time())
    r2_key = (
        f"snapshots/{project_id}/{build_id}/"
        f"{agent_number:02d}_{agent_type}.webp"
    )

    # Find sandbox URL from the build's project
    # In production, this would look up the sandbox assigned to this build
    preview_url = f"https://build-{build_id}.{settings.PREVIEW_DOMAIN}"

    screenshot_url = None
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            try:
                page = await browser.new_page(
                    viewport={"width": 1280, "height": 800}
                )
                await page.goto(
                    f"{preview_url}/",
                    timeout=5000,
                    wait_until="networkidle",
                )

                # Wait for React hydration — #root must have children
                try:
                    await page.wait_for_function(
                        "document.getElementById('root') && "
                        "document.getElementById('root').children.length > 0",
                        timeout=5000,
                    )
                except Exception:
                    logger.warning(
                        "snapshot_hydration_timeout",
                        build_id=build_id,
                        agent_type=agent_type,
                    )

                screenshot_bytes = await page.screenshot(
                    full_page=True,
                    type="png",
                )
            finally:
                await browser.close()

        # Upload to R2
        await storage_service.upload_file(
            key=r2_key,
            content=screenshot_bytes,
            content_type="image/webp",
        )
        screenshot_url = await storage_service.generate_presigned_url(r2_key)

    except Exception as exc:
        logger.error(
            "snapshot_capture_failed",
            build_id=build_id,
            agent_type=agent_type,
            error=str(exc),
        )
        # Don't fail the build — snapshot is a best-effort feature
        screenshot_url = None

    # Create DB record
    build_uuid = uuid.UUID(build_id)
    project_uuid = uuid.UUID(project_id)

    snapshot = BuildSnapshot(
        build_id=build_uuid,
        project_id=project_uuid,
        snapshot_index=agent_number,
        label=agent_type,
        screenshot_url=screenshot_url,
    )
    session.add(snapshot)
    await session.flush()

    # Publish Redis event for real-time streaming
    snapshot_data = {
        "id": str(snapshot.id),
        "build_id": build_id,
        "project_id": project_id,
        "snapshot_index": agent_number,
        "label": agent_type,
        "screenshot_url": screenshot_url,
        "created_at": snapshot.created_at.isoformat()
        if snapshot.created_at
        else datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }
    await publish_event(f"build:snapshot:{build_id}", snapshot_data)

    logger.info(
        "snapshot_captured",
        build_id=build_id,
        agent_type=agent_type,
        agent_number=agent_number,
        r2_key=r2_key,
    )

    return snapshot


async def get_snapshots(
    project_id: str,
    user_id: str,
    build_id: str | None,
    session: AsyncSession,
) -> list[BuildSnapshot]:
    """
    Get snapshots for a project/build.

    Verifies project ownership first.
    If build_id is provided: snapshots for that specific build.
    If None: snapshots for the latest completed build.
    """
    project_uuid = uuid.UUID(project_id)
    user_uuid = uuid.UUID(user_id)

    # Verify ownership
    ownership_stmt = select(Project).where(
        Project.id == project_uuid,
        Project.user_id == user_uuid,
    )
    ownership_result = await session.execute(ownership_stmt)
    if ownership_result.scalar_one_or_none() is None:
        raise LookupError(
            f"Project {project_id} not found or access denied"
        )

    if build_id:
        build_uuid = uuid.UUID(build_id)
        stmt = (
            select(BuildSnapshot)
            .where(
                BuildSnapshot.project_id == project_uuid,
                BuildSnapshot.build_id == build_uuid,
            )
            .order_by(BuildSnapshot.snapshot_index.asc())
        )
    else:
        # Find the latest completed build for this project
        latest_build_stmt = (
            select(Build.id)
            .where(
                Build.project_id == project_uuid,
                Build.status == BuildStatus.succeeded,
            )
            .order_by(Build.completed_at.desc())
            .limit(1)
        )
        latest_result = await session.execute(latest_build_stmt)
        latest_build_id = latest_result.scalar_one_or_none()

        if latest_build_id is None:
            return []

        stmt = (
            select(BuildSnapshot)
            .where(
                BuildSnapshot.project_id == project_uuid,
                BuildSnapshot.build_id == latest_build_id,
            )
            .order_by(BuildSnapshot.snapshot_index.asc())
        )

    result = await session.execute(stmt)
    return list(result.scalars().all())

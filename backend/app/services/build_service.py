"""
Build service — build lifecycle, agent orchestration coordination.
"""

from __future__ import annotations

import uuid

import structlog
from sqlalchemy import select, update as sa_update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.build import Build, BuildStatus
from app.models.project import Project

logger = structlog.get_logger()


async def start_build(
    project_id: str,
    user_id: str,
    pipeline_id: str | None,
    incremental: bool,
    session: AsyncSession,
) -> Build:
    """Start a new build for a project."""
    project = await _verify_project_ownership(project_id, user_id, session)

    build = Build(
        project_id=uuid.UUID(project_id),
        user_id=uuid.UUID(user_id),
        pipeline_run_id=uuid.UUID(pipeline_id) if pipeline_id else uuid.uuid4(),
        status=BuildStatus.pending,
    )
    session.add(build)
    await session.flush()

    logger.info(
        "build_started",
        build_id=str(build.id),
        project_id=project_id,
        incremental=incremental,
    )
    return build


async def get_build(
    build_id: str,
    user_id: str,
    session: AsyncSession,
) -> Build:
    """Get a build by ID (verifies ownership via project)."""
    stmt = (
        select(Build)
        .join(Project, Build.project_id == Project.id)
        .where(
            Build.id == uuid.UUID(build_id),
            Project.user_id == uuid.UUID(user_id),
        )
    )
    result = await session.execute(stmt)
    build = result.scalar_one_or_none()
    if build is None:
        raise LookupError(f"Build {build_id} not found or access denied")
    return build


async def list_builds(
    project_id: str,
    user_id: str,
    session: AsyncSession,
) -> list[Build]:
    """List all builds for a project."""
    await _verify_project_ownership(project_id, user_id, session)

    stmt = (
        select(Build)
        .where(Build.project_id == uuid.UUID(project_id))
        .order_by(Build.created_at.desc())
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def cancel_build(
    build_id: str,
    user_id: str,
    reason: str | None,
    session: AsyncSession,
) -> Build:
    """Cancel a running build."""
    build = await get_build(build_id, user_id, session)

    if build.status not in (BuildStatus.pending, BuildStatus.building):
        raise ValueError(f"Cannot cancel build in status {build.status}")

    await session.execute(
        sa_update(Build)
        .where(Build.id == build.id)
        .values(status=BuildStatus.failed, error_summary=reason or "Cancelled by user")
    )
    await session.flush()

    logger.info("build_cancelled", build_id=build_id, reason=reason)
    return build


async def retry_build(
    build_id: str,
    user_id: str,
    from_agent: int | None,
    session: AsyncSession,
) -> Build:
    """Retry a failed build, optionally from a specific agent."""
    build = await get_build(build_id, user_id, session)

    if build.status != BuildStatus.failed:
        raise ValueError("Can only retry failed builds")

    new_build = Build(
        project_id=build.project_id,
        user_id=build.user_id,
        pipeline_run_id=build.pipeline_run_id,
        status=BuildStatus.pending,
    )
    session.add(new_build)
    await session.flush()

    logger.info(
        "build_retried",
        original_build_id=build_id,
        new_build_id=str(new_build.id),
        from_agent=from_agent,
    )
    return new_build


async def _verify_project_ownership(
    project_id: str,
    user_id: str,
    db: AsyncSession,
) -> Project:
    """Verify user owns the project."""
    stmt = select(Project).where(
        Project.id == uuid.UUID(project_id),
        Project.user_id == uuid.UUID(user_id),
    )
    result = await db.execute(stmt)
    project = result.scalar_one_or_none()
    if project is None:
        raise LookupError(f"Project {project_id} not found or access denied")
    return project

"""
Deployment service — deploy orchestration, canary management.
"""

from __future__ import annotations

import uuid

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.deployment import Deployment
from app.models.project import Project

logger = structlog.get_logger()


async def create_deployment(
    project_id: str,
    user_id: str,
    build_id: str,
    session: AsyncSession,
) -> Deployment:
    """Create a new deployment for a project."""
    await _verify_project_ownership(project_id, user_id, session)

    deployment = Deployment(
        project_id=uuid.UUID(project_id),
        build_id=uuid.UUID(build_id),
        user_id=uuid.UUID(user_id),
    )
    session.add(deployment)
    await session.flush()

    logger.info(
        "deployment_created",
        deployment_id=str(deployment.id),
        project_id=project_id,
    )
    return deployment


async def list_deployments(
    project_id: str,
    user_id: str,
    session: AsyncSession,
) -> list[Deployment]:
    """List all deployments for a project."""
    await _verify_project_ownership(project_id, user_id, session)

    stmt = (
        select(Deployment)
        .where(Deployment.project_id == uuid.UUID(project_id))
        .order_by(Deployment.created_at.desc())
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_deployment(
    deployment_id: str,
    user_id: str,
    session: AsyncSession,
) -> Deployment:
    """Get a single deployment with ownership verification."""
    stmt = (
        select(Deployment)
        .join(Project, Deployment.project_id == Project.id)
        .where(
            Deployment.id == uuid.UUID(deployment_id),
            Project.user_id == uuid.UUID(user_id),
        )
    )
    result = await session.execute(stmt)
    deployment = result.scalar_one_or_none()
    if deployment is None:
        raise LookupError(f"Deployment {deployment_id} not found or access denied")
    return deployment


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

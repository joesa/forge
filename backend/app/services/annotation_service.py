"""
Annotation service — preview annotations for user feedback.

Users click on the preview pane to leave feedback at (x_pct, y_pct)
coordinates. Annotations can be resolved and are injected into AI
chat context so the build agents can address user feedback.
"""

import uuid

import structlog
from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.redis import publish_event
from app.models.annotation import Annotation
from app.models.project import Project

logger = structlog.get_logger(__name__)


async def _verify_project_ownership(
    project_id: uuid.UUID,
    user_id: uuid.UUID,
    session: AsyncSession,
) -> Project:
    """Verify user owns the project. Raises LookupError if not."""
    stmt = select(Project).where(
        Project.id == project_id,
        Project.user_id == user_id,
    )
    result = await session.execute(stmt)
    project = result.scalar_one_or_none()
    if project is None:
        raise LookupError(
            f"Project {project_id} not found or access denied"
        )
    return project


async def create_annotation(
    project_id: str,
    user_id: str,
    session_id: str,
    css_selector: str,
    route: str,
    comment: str,
    x_pct: float,
    y_pct: float,
    session: AsyncSession,
) -> Annotation:
    """
    Create a new annotation on the preview.

    Validates coordinate ranges and creates DB record.
    Publishes Redis event for real-time sync.
    """
    project_uuid = uuid.UUID(project_id)
    user_uuid = uuid.UUID(user_id)

    # Verify ownership
    await _verify_project_ownership(project_uuid, user_uuid, session)

    # Validate coordinates (belt-and-suspenders — Pydantic also validates)
    if not (0.0 <= x_pct <= 1.0 and 0.0 <= y_pct <= 1.0):
        raise ValueError("Coordinates must be between 0.0 and 1.0")

    annotation = Annotation(
        project_id=project_uuid,
        user_id=user_uuid,
        x_pct=x_pct,
        y_pct=y_pct,
        page_route=route,
        css_selector=css_selector,
        session_id=session_id,
        content=comment,
        resolved=False,
    )
    session.add(annotation)
    await session.flush()

    # Publish event for real-time sync
    await publish_event(
        f"annotations:{project_id}",
        {
            "action": "created",
            "annotation_id": str(annotation.id),
            "route": route,
            "comment": comment,
        },
    )

    logger.info(
        "annotation_created",
        project_id=project_id,
        annotation_id=str(annotation.id),
        route=route,
        user_id=user_id,
    )

    return annotation


async def get_annotations(
    project_id: str,
    user_id: str,
    include_resolved: bool,
    session: AsyncSession,
) -> list[Annotation]:
    """
    Get annotations for a project.

    Verifies project ownership first.
    Returns unresolved by default, or all if include_resolved=True.
    """
    project_uuid = uuid.UUID(project_id)
    user_uuid = uuid.UUID(user_id)

    # Verify ownership
    await _verify_project_ownership(project_uuid, user_uuid, session)

    stmt = select(Annotation).where(
        Annotation.project_id == project_uuid,
    )
    if not include_resolved:
        stmt = stmt.where(Annotation.resolved == False)  # noqa: E712

    stmt = stmt.order_by(Annotation.created_at.desc())

    result = await session.execute(stmt)
    return list(result.scalars().all())


async def resolve_annotation(
    annotation_id: str,
    user_id: str,
    session: AsyncSession,
) -> Annotation:
    """
    Mark an annotation as resolved.

    Requires user to own the project the annotation belongs to.
    """
    annotation_uuid = uuid.UUID(annotation_id)
    user_uuid = uuid.UUID(user_id)

    # Fetch annotation
    stmt = select(Annotation).where(Annotation.id == annotation_uuid)
    result = await session.execute(stmt)
    annotation = result.scalar_one_or_none()

    if annotation is None:
        raise LookupError(f"Annotation {annotation_id} not found")

    # Verify project ownership
    await _verify_project_ownership(
        annotation.project_id, user_uuid, session
    )

    annotation.resolved = True
    await session.flush()

    logger.info(
        "annotation_resolved",
        annotation_id=annotation_id,
        user_id=user_id,
    )

    return annotation


async def delete_annotation(
    annotation_id: str,
    user_id: str,
    session: AsyncSession,
) -> bool:
    """Delete a single annotation. Requires project ownership."""
    annotation_uuid = uuid.UUID(annotation_id)
    user_uuid = uuid.UUID(user_id)

    # Fetch annotation
    stmt = select(Annotation).where(Annotation.id == annotation_uuid)
    result = await session.execute(stmt)
    annotation = result.scalar_one_or_none()

    if annotation is None:
        raise LookupError(f"Annotation {annotation_id} not found")

    # Verify project ownership
    await _verify_project_ownership(
        annotation.project_id, user_uuid, session
    )

    await session.delete(annotation)
    await session.flush()

    logger.info(
        "annotation_deleted",
        annotation_id=annotation_id,
        user_id=user_id,
    )

    return True


async def clear_annotations(
    project_id: str,
    user_id: str,
    session: AsyncSession,
) -> int:
    """
    Delete all annotations for a project.

    Returns the number of annotations deleted.
    """
    project_uuid = uuid.UUID(project_id)
    user_uuid = uuid.UUID(user_id)

    # Verify ownership
    await _verify_project_ownership(project_uuid, user_uuid, session)

    stmt = (
        delete(Annotation)
        .where(Annotation.project_id == project_uuid)
        .returning(Annotation.id)
    )
    result = await session.execute(stmt)
    deleted_ids = result.scalars().all()
    count = len(deleted_ids)
    await session.flush()

    logger.info(
        "annotations_cleared",
        project_id=project_id,
        count=count,
        user_id=user_id,
    )

    return count


async def get_annotations_for_ai_context(
    project_id: str,
    session: AsyncSession,
) -> str:
    """
    Format unresolved annotations as a human-readable string
    for AI prompt injection.

    Output format:
      "The user has flagged these UI issues:
       1. [route] - [css_selector]: '[comment]'
       2. ..."
    """
    # Direct query — this is a system-level call from build agents,
    # not a user-facing route, so no ownership check needed.
    project_uuid = uuid.UUID(project_id)
    stmt = (
        select(Annotation)
        .where(
            Annotation.project_id == project_uuid,
            Annotation.resolved == False,  # noqa: E712
        )
        .order_by(Annotation.created_at.desc())
    )
    result = await session.execute(stmt)
    annotations = list(result.scalars().all())

    if not annotations:
        return ""

    lines = ["The user has flagged these UI issues:"]
    for i, ann in enumerate(annotations, 1):
        route = ann.page_route or "/"
        selector = ann.css_selector or "unknown"
        comment = ann.content
        lines.append(f"{i}. [{route}] - {selector}: '{comment}'")

    return "\n".join(lines)

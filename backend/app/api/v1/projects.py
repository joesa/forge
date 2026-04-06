"""
Projects API — v1.

All endpoints require authentication (enforced by AuthMiddleware).
Every route verifies project.user_id == current_user.id before
returning or modifying anything.

Endpoints:
  GET    /api/v1/projects                      — list user's projects
  POST   /api/v1/projects                      — create a project
  GET    /api/v1/projects/{id}                  — get project details
  PUT    /api/v1/projects/{id}                  — update project
  DELETE /api/v1/projects/{id}                  — delete project
  GET    /api/v1/projects/{id}/files            — file tree
  GET    /api/v1/projects/{id}/files/content    — read file
  PUT    /api/v1/projects/{id}/files/content    — write file
  DELETE /api/v1/projects/{id}/files            — delete file
  POST   /api/v1/projects/{id}/files/rename     — rename file
"""

import uuid

import structlog
from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_read_session, get_write_session
from app.schemas.projects import (
    FileContentResponse,
    FileRenameRequest,
    FileSaveRequest,
    FileTreeResponse,
    MessageResponse,
    ProjectCreateRequest,
    ProjectListResponse,
    ProjectResponse,
    ProjectUpdateRequest,
)
from app.services import project_service
from app.services.auth_service import get_or_create_user_on_login

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/v1/projects", tags=["projects"])


# ── Helpers ──────────────────────────────────────────────────────────


def _extract_user_id(request: Request) -> uuid.UUID:
    """Pull user ID from the JWT payload attached by AuthMiddleware."""
    payload = getattr(request.state, "user", None)
    if not payload:
        raise ValueError("No user payload in request state")
    sub = payload.get("sub")
    if not sub:
        raise ValueError("JWT missing 'sub' claim")
    return uuid.UUID(sub)


# ── Project CRUD ─────────────────────────────────────────────────────


@router.get("", response_model=ProjectListResponse)
async def list_projects(
    request: Request,
    status: str | None = Query(default=None),
    read_session: AsyncSession = Depends(get_read_session),
) -> ProjectListResponse | JSONResponse:
    """List all projects owned by the authenticated user."""
    try:
        user_id = _extract_user_id(request)
    except ValueError as exc:
        return JSONResponse(status_code=401, content={"detail": str(exc)})

    try:
        projects = await project_service.list_projects(
            user_id=user_id,
            session=read_session,
            status=status,
        )
        return ProjectListResponse(
            items=[ProjectResponse.model_validate(p) for p in projects],
            count=len(projects),
        )
    except Exception as exc:
        logger.error("list_projects_failed", error=str(exc), user_id=str(user_id))
        return JSONResponse(
            status_code=500, content={"detail": "Failed to list projects"}
        )


@router.post("", response_model=ProjectResponse, status_code=201)
async def create_project(
    body: ProjectCreateRequest,
    request: Request,
    write_session: AsyncSession = Depends(get_write_session),
) -> ProjectResponse | JSONResponse:
    """Create a new project."""
    try:
        user_id = _extract_user_id(request)
    except ValueError as exc:
        return JSONResponse(status_code=401, content={"detail": str(exc)})

    # Safety net: ensure the user row exists before the FK-constrained INSERT.
    # This handles users who were logged in before the login flow was fixed
    # (their Nhost token is valid but they have no row in our users table).
    jwt_payload = getattr(request.state, "user", {})
    email = jwt_payload.get("email", "")
    display_name = jwt_payload.get("displayName", "") or jwt_payload.get("display_name", "")
    if email:
        try:
            await get_or_create_user_on_login(
                nhost_user_id=str(user_id),
                email=email,
                display_name=display_name,
            )
        except Exception as upsert_exc:
            logger.warning("user_upsert_on_create_project_failed", error=str(upsert_exc))

    try:
        project = await project_service.create_project(
            user_id=user_id,
            name=body.name,
            description=body.description,
            framework=body.framework,
            session=write_session,
        )
        return ProjectResponse.model_validate(project)
    except Exception as exc:
        logger.error("create_project_failed", error=str(exc), user_id=str(user_id))
        # Re-raise HTTPExceptions (e.g. invalid framework)
        from fastapi import HTTPException

        if isinstance(exc, HTTPException):
            return JSONResponse(
                status_code=exc.status_code, content={"detail": exc.detail}
            )
        return JSONResponse(
            status_code=500, content={"detail": "Failed to create project"}
        )


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: uuid.UUID,
    request: Request,
    read_session: AsyncSession = Depends(get_read_session),
) -> ProjectResponse | JSONResponse:
    """Get a project by ID (must be owner)."""
    try:
        user_id = _extract_user_id(request)
    except ValueError as exc:
        return JSONResponse(status_code=401, content={"detail": str(exc)})

    try:
        project = await project_service.get_project(
            project_id=project_id,
            user_id=user_id,
            session=read_session,
        )
        return ProjectResponse.model_validate(project)
    except Exception as exc:
        from fastapi import HTTPException

        if isinstance(exc, HTTPException):
            return JSONResponse(
                status_code=exc.status_code, content={"detail": exc.detail}
            )
        logger.error("get_project_failed", error=str(exc))
        return JSONResponse(
            status_code=500, content={"detail": "Failed to get project"}
        )


@router.put("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: uuid.UUID,
    body: ProjectUpdateRequest,
    request: Request,
    write_session: AsyncSession = Depends(get_write_session),
) -> ProjectResponse | JSONResponse:
    """Update a project (must be owner)."""
    try:
        user_id = _extract_user_id(request)
    except ValueError as exc:
        return JSONResponse(status_code=401, content={"detail": str(exc)})

    # Build updates dict from provided fields only
    updates = body.model_dump(exclude_unset=True)

    try:
        project = await project_service.update_project(
            project_id=project_id,
            user_id=user_id,
            updates=updates,
            session=write_session,
        )
        return ProjectResponse.model_validate(project)
    except Exception as exc:
        from fastapi import HTTPException

        if isinstance(exc, HTTPException):
            return JSONResponse(
                status_code=exc.status_code, content={"detail": exc.detail}
            )
        logger.error("update_project_failed", error=str(exc))
        return JSONResponse(
            status_code=500, content={"detail": "Failed to update project"}
        )


@router.delete("/{project_id}")
async def delete_project(
    project_id: uuid.UUID,
    request: Request,
    write_session: AsyncSession = Depends(get_write_session),
) -> Response:
    """Delete a project and all its files (must be owner)."""
    try:
        user_id = _extract_user_id(request)
    except ValueError as exc:
        return JSONResponse(status_code=401, content={"detail": str(exc)})

    try:
        await project_service.delete_project(
            project_id=project_id,
            user_id=user_id,
            session=write_session,
        )
        return Response(status_code=204)
    except Exception as exc:
        from fastapi import HTTPException

        if isinstance(exc, HTTPException):
            return JSONResponse(
                status_code=exc.status_code, content={"detail": exc.detail}
            )
        logger.error("delete_project_failed", error=str(exc))
        return JSONResponse(
            status_code=500, content={"detail": "Failed to delete project"}
        )


# ── File Operations ──────────────────────────────────────────────────


@router.get("/{project_id}/files", response_model=FileTreeResponse)
async def get_file_tree(
    project_id: uuid.UUID,
    request: Request,
    read_session: AsyncSession = Depends(get_read_session),
) -> FileTreeResponse | JSONResponse:
    """Get the file tree for a project."""
    try:
        user_id = _extract_user_id(request)
    except ValueError as exc:
        return JSONResponse(status_code=401, content={"detail": str(exc)})

    try:
        tree_data = await project_service.get_file_tree(
            project_id=project_id,
            user_id=user_id,
            session=read_session,
        )
        return tree_data
    except Exception as exc:
        from fastapi import HTTPException

        if isinstance(exc, HTTPException):
            return JSONResponse(
                status_code=exc.status_code, content={"detail": exc.detail}
            )
        logger.error("get_file_tree_failed", error=str(exc))
        return JSONResponse(
            status_code=500, content={"detail": "Failed to get file tree"}
        )


@router.get("/{project_id}/files/content", response_model=FileContentResponse)
async def get_file_content(
    project_id: uuid.UUID,
    request: Request,
    path: str = Query(..., min_length=1),
    read_session: AsyncSession = Depends(get_read_session),
) -> FileContentResponse | JSONResponse:
    """Read file content from R2."""
    try:
        user_id = _extract_user_id(request)
    except ValueError as exc:
        return JSONResponse(status_code=401, content={"detail": str(exc)})

    try:
        content = await project_service.get_file_content(
            project_id=project_id,
            user_id=user_id,
            path=path,
            session=read_session,
        )
        return FileContentResponse(
            project_id=project_id,
            path=path,
            content=content,
        )
    except Exception as exc:
        from fastapi import HTTPException

        if isinstance(exc, HTTPException):
            return JSONResponse(
                status_code=exc.status_code, content={"detail": exc.detail}
            )
        logger.error("get_file_content_failed", error=str(exc))
        return JSONResponse(
            status_code=500, content={"detail": "Failed to read file"}
        )


@router.put("/{project_id}/files/content", response_model=MessageResponse)
async def save_file_content(
    project_id: uuid.UUID,
    body: FileSaveRequest,
    request: Request,
    write_session: AsyncSession = Depends(get_write_session),
) -> MessageResponse | JSONResponse:
    """Write file content to R2."""
    try:
        user_id = _extract_user_id(request)
    except ValueError as exc:
        return JSONResponse(status_code=401, content={"detail": str(exc)})

    try:
        await project_service.save_file_content(
            project_id=project_id,
            user_id=user_id,
            path=body.path,
            content=body.content,
            session=write_session,
        )
        return MessageResponse(message="File saved successfully")
    except Exception as exc:
        from fastapi import HTTPException

        if isinstance(exc, HTTPException):
            return JSONResponse(
                status_code=exc.status_code, content={"detail": exc.detail}
            )
        logger.error("save_file_content_failed", error=str(exc))
        return JSONResponse(
            status_code=500, content={"detail": "Failed to save file"}
        )


@router.delete("/{project_id}/files", response_model=MessageResponse)
async def delete_file(
    project_id: uuid.UUID,
    request: Request,
    path: str = Query(..., min_length=1),
    write_session: AsyncSession = Depends(get_write_session),
) -> MessageResponse | JSONResponse:
    """Delete a file from R2."""
    try:
        user_id = _extract_user_id(request)
    except ValueError as exc:
        return JSONResponse(status_code=401, content={"detail": str(exc)})

    try:
        await project_service.delete_file(
            project_id=project_id,
            user_id=user_id,
            path=path,
            session=write_session,
        )
        return MessageResponse(message="File deleted successfully")
    except Exception as exc:
        from fastapi import HTTPException

        if isinstance(exc, HTTPException):
            return JSONResponse(
                status_code=exc.status_code, content={"detail": exc.detail}
            )
        logger.error("delete_file_failed", error=str(exc))
        return JSONResponse(
            status_code=500, content={"detail": "Failed to delete file"}
        )


@router.post("/{project_id}/files/rename", response_model=MessageResponse)
async def rename_file(
    project_id: uuid.UUID,
    body: FileRenameRequest,
    request: Request,
    write_session: AsyncSession = Depends(get_write_session),
) -> MessageResponse | JSONResponse:
    """Rename/move a file in R2."""
    try:
        user_id = _extract_user_id(request)
    except ValueError as exc:
        return JSONResponse(status_code=401, content={"detail": str(exc)})

    try:
        await project_service.rename_file(
            project_id=project_id,
            user_id=user_id,
            old_path=body.old_path,
            new_path=body.new_path,
            session=write_session,
        )
        return MessageResponse(message="File renamed successfully")
    except Exception as exc:
        from fastapi import HTTPException

        if isinstance(exc, HTTPException):
            return JSONResponse(
                status_code=exc.status_code, content={"detail": exc.detail}
            )
        logger.error("rename_file_failed", error=str(exc))
        return JSONResponse(
            status_code=500, content={"detail": "Failed to rename file"}
        )


@router.post("/{project_id}/files", response_model=MessageResponse, status_code=201)
async def create_file(
    project_id: uuid.UUID,
    request: Request,
    write_session: AsyncSession = Depends(get_write_session),
) -> MessageResponse | JSONResponse:
    """Create a new file in the project."""
    try:
        user_id = _extract_user_id(request)
    except ValueError as exc:
        return JSONResponse(status_code=401, content={"detail": str(exc)})

    try:
        body = await request.json()
        path = body.get("path", "")
        content = body.get("content", "")
        await project_service.save_file_content(
            project_id=project_id,
            user_id=user_id,
            file_path=path,
            content=content,
            session=write_session,
        )
        return MessageResponse(message="File created successfully")
    except Exception as exc:
        logger.error("create_file_failed", error=str(exc))
        return JSONResponse(status_code=500, content={"detail": "Failed to create file"})


@router.get("/{project_id}/builds")
async def list_project_builds(
    project_id: uuid.UUID,
    request: Request,
    read_session: AsyncSession = Depends(get_read_session),
) -> JSONResponse:
    """List all builds for a project."""
    try:
        user_id = _extract_user_id(request)
    except ValueError as exc:
        return JSONResponse(status_code=401, content={"detail": str(exc)})

    try:
        from app.services.build_service import list_builds
        builds = await list_builds(str(project_id), str(user_id), read_session)
        return JSONResponse(content={"builds": [
            {
                "id": str(b.id),
                "status": b.status.value if hasattr(b.status, "value") else str(b.status),
                "build_number": b.build_number,
                "created_at": b.created_at.isoformat(),
                "started_at": b.started_at.isoformat() if b.started_at else None,
                "completed_at": b.completed_at.isoformat() if b.completed_at else None,
                "error_summary": b.error_summary,
            } for b in builds
        ]})
    except LookupError as exc:
        return JSONResponse(status_code=404, content={"detail": str(exc)})
    except Exception as exc:
        logger.error("list_builds_failed", error=str(exc))
        return JSONResponse(status_code=500, content={"detail": "Failed to list builds"})


@router.get("/{project_id}/deployments")
async def list_project_deployments(
    project_id: uuid.UUID,
    request: Request,
    read_session: AsyncSession = Depends(get_read_session),
) -> JSONResponse:
    """List all deployments for a project."""
    try:
        user_id = _extract_user_id(request)
    except ValueError as exc:
        return JSONResponse(status_code=401, content={"detail": str(exc)})

    try:
        from app.services.deployment_service import list_deployments
        deployments = await list_deployments(str(project_id), str(user_id), read_session)
        return JSONResponse(content={"deployments": [
            {
                "id": str(d.id),
                "status": d.status.value if hasattr(d.status, "value") else str(d.status),
                "url": d.url,
                "created_at": d.created_at.isoformat(),
            } for d in deployments
        ]})
    except LookupError as exc:
        return JSONResponse(status_code=404, content={"detail": str(exc)})
    except Exception as exc:
        logger.error("list_deployments_failed", error=str(exc))
        return JSONResponse(status_code=500, content={"detail": "Failed to list deployments"})


@router.post("/{project_id}/deploy")
async def deploy_project(
    project_id: uuid.UUID,
    request: Request,
    write_session: AsyncSession = Depends(get_write_session),
) -> JSONResponse:
    """Trigger a deployment for the project."""
    try:
        user_id = _extract_user_id(request)
    except ValueError as exc:
        return JSONResponse(status_code=401, content={"detail": str(exc)})

    try:
        from app.services.deployment_service import create_deployment
        deployment = await create_deployment(str(project_id), str(user_id), write_session)
        return JSONResponse(content={
            "id": str(deployment.id),
            "status": deployment.status.value if hasattr(deployment.status, "value") else str(deployment.status),
            "url": deployment.url,
            "created_at": deployment.created_at.isoformat(),
        })
    except LookupError as exc:
        return JSONResponse(status_code=404, content={"detail": str(exc)})
    except Exception as exc:
        logger.error("deploy_failed", error=str(exc))
        return JSONResponse(status_code=500, content={"detail": "Failed to deploy"})

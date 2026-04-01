"""
Project service — business logic for CRUD and file operations.

Architecture rules:
  • DB reads → read session (replica)
  • DB writes → write session (primary)
  • File storage → Cloudflare R2 via storage_service
  • Every data access checks user_id ownership
"""

import os
import uuid

import structlog
from botocore.exceptions import ClientError
from fastapi import HTTPException
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.project import Project, ProjectFramework, ProjectStatus
from app.services import storage_service

logger = structlog.get_logger(__name__)

# R2 key prefix: projects/{project_id}/files/...
_FILE_PREFIX = "projects/{project_id}/files/"


def _file_key(project_id: uuid.UUID, sanitized_path: str) -> str:
    """Build the R2 object key for a project file.

    Expects a path already processed by ``_sanitize_path``.
    """
    return f"projects/{project_id}/files/{sanitized_path}"


def _file_prefix(project_id: uuid.UUID) -> str:
    """Build the R2 key prefix for all files in a project."""
    return f"projects/{project_id}/files/"


def _sanitize_path(path: str) -> str:
    """
    Sanitize a user-supplied file path.

    Security checks:
      1. No null bytes (could truncate strings in C-backed systems)
      2. No backslash path separators (Windows-style traversal)
      3. Strip leading slashes (no absolute paths)
      4. Normalize path (collapse ./ and //)
      5. Reject any component that is '..' (directory traversal)
      6. Reject empty result
    """
    # Block null bytes
    if "\x00" in path:
        raise HTTPException(
            status_code=400, detail="Invalid file path: null bytes not allowed"
        )

    # Block backslash (Windows-style traversal)
    if "\\" in path:
        raise HTTPException(
            status_code=400, detail="Invalid file path: backslash not allowed"
        )

    # Strip leading slashes
    clean = path.lstrip("/")

    # Normalize: collapse ./  and //  but keep relative
    # Use posixpath to avoid platform-dependent behavior
    import posixpath
    clean = posixpath.normpath(clean)

    # After normpath, '..' traversal shows up as literal '..' components
    parts = clean.split("/")
    if ".." in parts:
        raise HTTPException(
            status_code=400, detail="Invalid file path: path traversal detected"
        )

    # Reject empty or root-only path
    if not clean or clean == ".":
        raise HTTPException(
            status_code=400, detail="Invalid file path: empty path"
        )

    return clean


# ── Project CRUD ─────────────────────────────────────────────────────


async def create_project(
    user_id: uuid.UUID,
    name: str,
    description: str | None,
    framework: str | None,
    session: AsyncSession,
) -> Project:
    """
    Create a new project for the given user.

    Uses the write session (primary DB).
    """
    # Validate framework if provided
    fw = None
    if framework:
        try:
            fw = ProjectFramework(framework)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid framework: {framework}. "
                f"Valid options: {[e.value for e in ProjectFramework]}",
            )

    project = Project(
        id=uuid.uuid4(),
        user_id=user_id,
        name=name,
        description=description,
        framework=fw,
    )
    session.add(project)
    await session.flush()
    await session.refresh(project)

    logger.info(
        "project_created",
        project_id=str(project.id),
        user_id=str(user_id),
        name=name,
    )
    return project


async def get_project(
    project_id: uuid.UUID,
    user_id: uuid.UUID,
    session: AsyncSession,
) -> Project:
    """
    Fetch a project by ID, verifying ownership.

    Returns 404 if not found or not owned by user
    (never reveals whether the project exists to non-owners).
    """
    stmt = select(Project).where(
        Project.id == project_id,
        Project.user_id == user_id,
    )
    result = await session.execute(stmt)
    project = result.scalar_one_or_none()

    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    return project


async def list_projects(
    user_id: uuid.UUID,
    session: AsyncSession,
    status: str | None = None,
) -> list[Project]:
    """
    List all projects owned by user, optionally filtered by status.

    Uses the read session (replica DB).
    """
    stmt = select(Project).where(Project.user_id == user_id)

    if status:
        try:
            status_enum = ProjectStatus(status)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid status: {status}. "
                f"Valid options: {[e.value for e in ProjectStatus]}",
            )
        stmt = stmt.where(Project.status == status_enum)

    stmt = stmt.order_by(Project.updated_at.desc())
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def update_project(
    project_id: uuid.UUID,
    user_id: uuid.UUID,
    updates: dict,
    session: AsyncSession,
) -> Project:
    """
    Update a project. Only the owner can modify.

    Uses the write session (primary DB).
    """
    # First verify ownership
    project = await get_project(project_id, user_id, session)

    # Build update values
    values: dict = {}
    if "name" in updates and updates["name"] is not None:
        values["name"] = updates["name"]
    if "description" in updates:
        values["description"] = updates["description"]
    if "status" in updates and updates["status"] is not None:
        try:
            values["status"] = ProjectStatus(updates["status"])
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid status: {updates['status']}. "
                f"Valid options: {[e.value for e in ProjectStatus]}",
            )
    if "framework" in updates and updates["framework"] is not None:
        try:
            values["framework"] = ProjectFramework(updates["framework"])
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid framework: {updates['framework']}. "
                f"Valid options: {[e.value for e in ProjectFramework]}",
            )

    if values:
        stmt = (
            update(Project)
            .where(Project.id == project_id, Project.user_id == user_id)
            .values(**values)
        )
        await session.execute(stmt)
        await session.flush()
        await session.refresh(project)

    logger.info(
        "project_updated",
        project_id=str(project_id),
        user_id=str(user_id),
        fields=list(values.keys()),
    )
    return project


async def delete_project(
    project_id: uuid.UUID,
    user_id: uuid.UUID,
    session: AsyncSession,
) -> None:
    """
    Delete a project and all its R2 files.

    Uses the write session (primary DB).
    """
    # Verify ownership
    project = await get_project(project_id, user_id, session)

    # Delete all files from R2
    try:
        prefix = _file_prefix(project_id)
        await storage_service.delete_prefix(prefix)
    except ClientError:
        logger.warning(
            "r2_cleanup_failed_on_delete",
            project_id=str(project_id),
        )
        # Continue with DB deletion even if R2 cleanup fails

    await session.delete(project)
    await session.flush()

    logger.info(
        "project_deleted",
        project_id=str(project_id),
        user_id=str(user_id),
    )


# ── File Operations ──────────────────────────────────────────────────


async def get_file_tree(
    project_id: uuid.UUID,
    user_id: uuid.UUID,
    session: AsyncSession,
) -> dict:
    """
    Build a nested file tree structure from R2 keys.

    Returns a dict like:
    {
        "project_id": "...",
        "tree": [
            {"name": "src", "path": "src", "type": "directory", "children": [
                {"name": "index.tsx", "path": "src/index.tsx", "type": "file"}
            ]}
        ]
    }
    """
    # Verify ownership
    await get_project(project_id, user_id, session)

    prefix = _file_prefix(project_id)
    keys = await storage_service.list_files(prefix)

    # Strip prefix to get relative paths
    prefix_len = len(prefix)
    relative_paths = [k[prefix_len:] for k in keys if len(k) > prefix_len]

    # Build nested tree
    tree: dict = {}
    for path in relative_paths:
        parts = path.split("/")
        current = tree
        for i, part in enumerate(parts):
            if part not in current:
                current[part] = {}
            current = current[part]

    def _build_nodes(subtree: dict, parent_path: str = "") -> list[dict]:
        nodes: list[dict] = []
        for name, children in sorted(subtree.items()):
            full_path = f"{parent_path}/{name}" if parent_path else name
            if children:  # Has children → directory
                nodes.append(
                    {
                        "name": name,
                        "path": full_path,
                        "type": "directory",
                        "children": _build_nodes(children, full_path),
                    }
                )
            else:  # Leaf → file
                nodes.append(
                    {
                        "name": name,
                        "path": full_path,
                        "type": "file",
                        "children": None,
                    }
                )
        return nodes

    return {
        "project_id": str(project_id),
        "tree": _build_nodes(tree),
    }


async def get_file_content(
    project_id: uuid.UUID,
    user_id: uuid.UUID,
    path: str,
    session: AsyncSession,
) -> str:
    """
    Read file content from R2.

    Returns the file content as a UTF-8 string.
    """
    # Verify ownership
    await get_project(project_id, user_id, session)

    clean_path = _sanitize_path(path)
    key = _file_key(project_id, clean_path)

    try:
        data = await storage_service.download_file(key)
        return data.decode("utf-8")
    except ClientError as exc:
        error_code = exc.response.get("Error", {}).get("Code", "")
        if error_code in ("NoSuchKey", "404"):
            raise HTTPException(status_code=404, detail="File not found")
        raise HTTPException(status_code=500, detail="Failed to read file")


async def save_file_content(
    project_id: uuid.UUID,
    user_id: uuid.UUID,
    path: str,
    content: str,
    session: AsyncSession,
) -> None:
    """
    Write file content to R2.

    Overwrites existing files, creates new ones.
    """
    # Verify ownership
    await get_project(project_id, user_id, session)

    clean_path = _sanitize_path(path)
    key = _file_key(project_id, clean_path)

    # Guess content type from extension
    ext = os.path.splitext(clean_path)[1].lower()
    content_types = {
        ".ts": "text/typescript",
        ".tsx": "text/typescript",
        ".js": "text/javascript",
        ".jsx": "text/javascript",
        ".json": "application/json",
        ".html": "text/html",
        ".css": "text/css",
        ".md": "text/markdown",
        ".py": "text/x-python",
        ".yaml": "text/yaml",
        ".yml": "text/yaml",
        ".toml": "text/toml",
        ".svg": "image/svg+xml",
    }
    content_type = content_types.get(ext, "text/plain")

    await storage_service.upload_file(
        key=key,
        content=content.encode("utf-8"),
        content_type=content_type,
    )

    logger.info(
        "file_saved",
        project_id=str(project_id),
        path=clean_path,
        size=len(content),
    )


async def delete_file(
    project_id: uuid.UUID,
    user_id: uuid.UUID,
    path: str,
    session: AsyncSession,
) -> None:
    """Delete a single file from R2."""
    # Verify ownership
    await get_project(project_id, user_id, session)

    clean_path = _sanitize_path(path)
    key = _file_key(project_id, clean_path)

    await storage_service.delete_file(key)

    logger.info(
        "file_deleted",
        project_id=str(project_id),
        path=clean_path,
    )


async def rename_file(
    project_id: uuid.UUID,
    user_id: uuid.UUID,
    old_path: str,
    new_path: str,
    session: AsyncSession,
) -> None:
    """
    Rename/move a file in R2.

    R2/S3 has no native rename — we copy + delete.
    """
    # Verify ownership
    await get_project(project_id, user_id, session)

    old_clean = _sanitize_path(old_path)
    new_clean = _sanitize_path(new_path)

    old_key = _file_key(project_id, old_clean)
    new_key = _file_key(project_id, new_clean)

    # Download existing content
    try:
        data = await storage_service.download_file(old_key)
    except ClientError as exc:
        error_code = exc.response.get("Error", {}).get("Code", "")
        if error_code in ("NoSuchKey", "404"):
            raise HTTPException(status_code=404, detail="Source file not found")
        raise HTTPException(status_code=500, detail="Failed to read source file")

    # Upload to new key
    ext = os.path.splitext(new_clean)[1].lower()
    content_types = {
        ".ts": "text/typescript",
        ".tsx": "text/typescript",
        ".js": "text/javascript",
        ".jsx": "text/javascript",
        ".json": "application/json",
        ".html": "text/html",
        ".css": "text/css",
        ".md": "text/markdown",
        ".py": "text/x-python",
    }
    content_type = content_types.get(ext, "text/plain")

    await storage_service.upload_file(
        key=new_key,
        content=data,
        content_type=content_type,
    )

    # Delete old key
    await storage_service.delete_file(old_key)

    logger.info(
        "file_renamed",
        project_id=str(project_id),
        old_path=old_clean,
        new_path=new_clean,
    )

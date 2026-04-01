"""
Tests for the Projects API — CRUD + file operations.

All external services (R2/S3, database) are mocked.
Never call real external APIs in tests (AGENTS.md rule #7).

Tests cover:
  - Full CRUD (create, read, update, delete projects)
  - Ownership isolation (user A cannot access user B's projects → 404)
  - File operations (tree, read, write, delete, rename)
  - Path traversal prevention
  - Invalid inputs (bad framework, bad status)
"""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient

# ── Constants ────────────────────────────────────────────────────────

USER_A_ID = str(uuid.uuid4())
USER_B_ID = str(uuid.uuid4())
PROJECT_ID = str(uuid.uuid4())
FAKE_ACCESS_TOKEN = "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.fake"

# Auth middleware mock context manager — reusable
_AUTH_PATCHES_A = {
    "kid": "test-kid",
    "sub": USER_A_ID,
}
_AUTH_PATCHES_B = {
    "kid": "test-kid",
    "sub": USER_B_ID,
}


def _auth_mocks(user_sub: str):
    """Return a context manager stack that bypasses AuthMiddleware for a given user."""
    return [
        patch(
            "app.middleware.auth._fetch_jwks",
            new_callable=AsyncMock,
            return_value={"keys": []},
        ),
        patch(
            "app.middleware.auth.jwt.get_unverified_header",
            return_value={"kid": "test-kid", "alg": "RS256"},
        ),
        patch(
            "app.middleware.auth._find_rsa_key",
            return_value={
                "kty": "RSA",
                "kid": "test-kid",
                "n": "x",
                "e": "y",
                "use": "sig",
            },
        ),
        patch(
            "app.middleware.auth.jwt.decode",
            return_value={"sub": user_sub, "exp": 9999999999},
        ),
    ]


def _make_fake_project(
    project_id: str = PROJECT_ID,
    user_id: str = USER_A_ID,
    name: str = "My App",
    description: str | None = "A test project",
    status: str = "draft",
    framework: str | None = "nextjs",
):
    """Create a mock Project ORM object."""
    project = MagicMock()
    project.id = uuid.UUID(project_id)
    project.user_id = uuid.UUID(user_id)
    project.name = name
    project.description = description
    project.status = status
    project.framework = framework
    project.created_at = datetime(2026, 3, 31, tzinfo=timezone.utc)
    project.updated_at = datetime(2026, 3, 31, tzinfo=timezone.utc)
    return project


def _auth_headers() -> dict[str, str]:
    """Return Authorization headers for tests."""
    return {"Authorization": f"Bearer {FAKE_ACCESS_TOKEN}"}


# ── Helper: apply auth mocks + session overrides ─────────────────────


def _apply_auth_and_session(user_sub: str, session_type: str = "read"):
    """
    Combined context manager to apply auth mocks and session overrides.

    Returns (patches_list, override_setup_fn, override_cleanup_fn).
    """
    patches = _auth_mocks(user_sub)
    mock_session = AsyncMock()

    from app.main import app
    from app.core.database import get_read_session, get_write_session

    target = get_read_session if session_type == "read" else get_write_session

    async def override_session():
        yield mock_session

    def setup():
        app.dependency_overrides[target] = override_session

    def cleanup():
        app.dependency_overrides.pop(target, None)

    return patches, mock_session, setup, cleanup


# ── POST /api/v1/projects ───────────────────────────────────────────


@pytest.mark.anyio
async def test_create_project_success(client: AsyncClient):
    """Create a project returns 201 with project data."""
    fake_project = _make_fake_project()
    patches = _auth_mocks(USER_A_ID)

    with patches[0], patches[1], patches[2], patches[3]:
        with patch(
            "app.api.v1.projects.project_service.create_project",
            new_callable=AsyncMock,
            return_value=fake_project,
        ):
            from app.main import app
            from app.core.database import get_write_session

            mock_session = AsyncMock()

            async def override_write():
                yield mock_session

            app.dependency_overrides[get_write_session] = override_write

            try:
                resp = await client.post(
                    "/api/v1/projects",
                    json={
                        "name": "My App",
                        "description": "A test project",
                        "framework": "nextjs",
                    },
                    headers=_auth_headers(),
                )

                assert resp.status_code == 201
                data = resp.json()
                assert data["name"] == "My App"
                assert data["description"] == "A test project"
                assert data["status"] == "draft"
                assert data["framework"] == "nextjs"
                assert data["id"] == PROJECT_ID
            finally:
                app.dependency_overrides.pop(get_write_session, None)


@pytest.mark.anyio
async def test_create_project_missing_name(client: AsyncClient):
    """Create project without name returns 422."""
    patches = _auth_mocks(USER_A_ID)

    with patches[0], patches[1], patches[2], patches[3]:
        resp = await client.post(
            "/api/v1/projects",
            json={"description": "No name provided"},
            headers=_auth_headers(),
        )
        assert resp.status_code == 422


@pytest.mark.anyio
async def test_create_project_no_auth(client: AsyncClient):
    """Create project without auth returns 401."""
    resp = await client.post(
        "/api/v1/projects",
        json={"name": "My App"},
    )
    assert resp.status_code == 401


# ── GET /api/v1/projects ─────────────────────────────────────────────


@pytest.mark.anyio
async def test_list_projects_success(client: AsyncClient):
    """List projects returns user's projects."""
    fake_projects = [
        _make_fake_project(project_id=str(uuid.uuid4()), name="App 1"),
        _make_fake_project(project_id=str(uuid.uuid4()), name="App 2"),
    ]
    patches = _auth_mocks(USER_A_ID)

    with patches[0], patches[1], patches[2], patches[3]:
        with patch(
            "app.api.v1.projects.project_service.list_projects",
            new_callable=AsyncMock,
            return_value=fake_projects,
        ):
            from app.main import app
            from app.core.database import get_read_session

            mock_session = AsyncMock()

            async def override_read():
                yield mock_session

            app.dependency_overrides[get_read_session] = override_read

            try:
                resp = await client.get(
                    "/api/v1/projects",
                    headers=_auth_headers(),
                )

                assert resp.status_code == 200
                data = resp.json()
                assert data["count"] == 2
                assert len(data["items"]) == 2
                assert data["items"][0]["name"] == "App 1"
                assert data["items"][1]["name"] == "App 2"
            finally:
                app.dependency_overrides.pop(get_read_session, None)


@pytest.mark.anyio
async def test_list_projects_empty(client: AsyncClient):
    """List projects returns empty list when user has no projects."""
    patches = _auth_mocks(USER_A_ID)

    with patches[0], patches[1], patches[2], patches[3]:
        with patch(
            "app.api.v1.projects.project_service.list_projects",
            new_callable=AsyncMock,
            return_value=[],
        ):
            from app.main import app
            from app.core.database import get_read_session

            mock_session = AsyncMock()

            async def override_read():
                yield mock_session

            app.dependency_overrides[get_read_session] = override_read

            try:
                resp = await client.get(
                    "/api/v1/projects",
                    headers=_auth_headers(),
                )

                assert resp.status_code == 200
                data = resp.json()
                assert data["count"] == 0
                assert data["items"] == []
            finally:
                app.dependency_overrides.pop(get_read_session, None)


@pytest.mark.anyio
async def test_list_projects_with_status_filter(client: AsyncClient):
    """List projects with status filter passes status to service."""
    patches = _auth_mocks(USER_A_ID)

    with patches[0], patches[1], patches[2], patches[3]:
        mock_list = AsyncMock(return_value=[])
        with patch(
            "app.api.v1.projects.project_service.list_projects",
            mock_list,
        ):
            from app.main import app
            from app.core.database import get_read_session

            mock_session = AsyncMock()

            async def override_read():
                yield mock_session

            app.dependency_overrides[get_read_session] = override_read

            try:
                resp = await client.get(
                    "/api/v1/projects?status=live",
                    headers=_auth_headers(),
                )

                assert resp.status_code == 200
                # Verify status was passed to service
                mock_list.assert_called_once()
                call_kwargs = mock_list.call_args
                assert call_kwargs.kwargs.get("status") == "live" or (
                    len(call_kwargs.args) > 2 and call_kwargs.args[2] == "live"
                )
            finally:
                app.dependency_overrides.pop(get_read_session, None)


# ── GET /api/v1/projects/{id} ───────────────────────────────────────


@pytest.mark.anyio
async def test_get_project_success(client: AsyncClient):
    """Get project by ID returns project data."""
    fake_project = _make_fake_project()
    patches = _auth_mocks(USER_A_ID)

    with patches[0], patches[1], patches[2], patches[3]:
        with patch(
            "app.api.v1.projects.project_service.get_project",
            new_callable=AsyncMock,
            return_value=fake_project,
        ):
            from app.main import app
            from app.core.database import get_read_session

            mock_session = AsyncMock()

            async def override_read():
                yield mock_session

            app.dependency_overrides[get_read_session] = override_read

            try:
                resp = await client.get(
                    f"/api/v1/projects/{PROJECT_ID}",
                    headers=_auth_headers(),
                )

                assert resp.status_code == 200
                data = resp.json()
                assert data["id"] == PROJECT_ID
                assert data["name"] == "My App"
            finally:
                app.dependency_overrides.pop(get_read_session, None)


@pytest.mark.anyio
async def test_get_project_not_found(client: AsyncClient):
    """Get non-existent project returns 404."""
    from fastapi import HTTPException

    patches = _auth_mocks(USER_A_ID)

    with patches[0], patches[1], patches[2], patches[3]:
        with patch(
            "app.api.v1.projects.project_service.get_project",
            new_callable=AsyncMock,
            side_effect=HTTPException(status_code=404, detail="Project not found"),
        ):
            from app.main import app
            from app.core.database import get_read_session

            mock_session = AsyncMock()

            async def override_read():
                yield mock_session

            app.dependency_overrides[get_read_session] = override_read

            try:
                fake_id = str(uuid.uuid4())
                resp = await client.get(
                    f"/api/v1/projects/{fake_id}",
                    headers=_auth_headers(),
                )

                assert resp.status_code == 404
                assert resp.json()["detail"] == "Project not found"
            finally:
                app.dependency_overrides.pop(get_read_session, None)


# ── Ownership isolation ──────────────────────────────────────────────


@pytest.mark.anyio
async def test_user_b_cannot_access_user_a_project(client: AsyncClient):
    """User B trying to access User A's project gets 404 (not 403)."""
    from fastapi import HTTPException

    # Authenticate as User B
    patches = _auth_mocks(USER_B_ID)

    with patches[0], patches[1], patches[2], patches[3]:
        # Service raises 404 because WHERE user_id = B finds nothing
        with patch(
            "app.api.v1.projects.project_service.get_project",
            new_callable=AsyncMock,
            side_effect=HTTPException(status_code=404, detail="Project not found"),
        ):
            from app.main import app
            from app.core.database import get_read_session

            mock_session = AsyncMock()

            async def override_read():
                yield mock_session

            app.dependency_overrides[get_read_session] = override_read

            try:
                resp = await client.get(
                    f"/api/v1/projects/{PROJECT_ID}",
                    headers=_auth_headers(),
                )

                # Must be 404, NOT 403 — don't reveal project exists
                assert resp.status_code == 404
                assert resp.json()["detail"] == "Project not found"
            finally:
                app.dependency_overrides.pop(get_read_session, None)


@pytest.mark.anyio
async def test_user_b_cannot_update_user_a_project(client: AsyncClient):
    """User B trying to update User A's project gets 404."""
    from fastapi import HTTPException

    patches = _auth_mocks(USER_B_ID)

    with patches[0], patches[1], patches[2], patches[3]:
        with patch(
            "app.api.v1.projects.project_service.update_project",
            new_callable=AsyncMock,
            side_effect=HTTPException(status_code=404, detail="Project not found"),
        ):
            from app.main import app
            from app.core.database import get_write_session

            mock_session = AsyncMock()

            async def override_write():
                yield mock_session

            app.dependency_overrides[get_write_session] = override_write

            try:
                resp = await client.put(
                    f"/api/v1/projects/{PROJECT_ID}",
                    json={"name": "Hacked Name"},
                    headers=_auth_headers(),
                )

                assert resp.status_code == 404
            finally:
                app.dependency_overrides.pop(get_write_session, None)


@pytest.mark.anyio
async def test_user_b_cannot_delete_user_a_project(client: AsyncClient):
    """User B trying to delete User A's project gets 404."""
    from fastapi import HTTPException

    patches = _auth_mocks(USER_B_ID)

    with patches[0], patches[1], patches[2], patches[3]:
        with patch(
            "app.api.v1.projects.project_service.delete_project",
            new_callable=AsyncMock,
            side_effect=HTTPException(status_code=404, detail="Project not found"),
        ):
            from app.main import app
            from app.core.database import get_write_session

            mock_session = AsyncMock()

            async def override_write():
                yield mock_session

            app.dependency_overrides[get_write_session] = override_write

            try:
                resp = await client.delete(
                    f"/api/v1/projects/{PROJECT_ID}",
                    headers=_auth_headers(),
                )

                assert resp.status_code == 404
            finally:
                app.dependency_overrides.pop(get_write_session, None)


@pytest.mark.anyio
async def test_user_b_cannot_read_user_a_files(client: AsyncClient):
    """User B trying to read User A's files gets 404."""
    from fastapi import HTTPException

    patches = _auth_mocks(USER_B_ID)

    with patches[0], patches[1], patches[2], patches[3]:
        with patch(
            "app.api.v1.projects.project_service.get_file_content",
            new_callable=AsyncMock,
            side_effect=HTTPException(status_code=404, detail="Project not found"),
        ):
            from app.main import app
            from app.core.database import get_read_session

            mock_session = AsyncMock()

            async def override_read():
                yield mock_session

            app.dependency_overrides[get_read_session] = override_read

            try:
                resp = await client.get(
                    f"/api/v1/projects/{PROJECT_ID}/files/content?path=src/index.tsx",
                    headers=_auth_headers(),
                )

                assert resp.status_code == 404
            finally:
                app.dependency_overrides.pop(get_read_session, None)


# ── PUT /api/v1/projects/{id} ───────────────────────────────────────


@pytest.mark.anyio
async def test_update_project_success(client: AsyncClient):
    """Update project returns updated data."""
    updated_project = _make_fake_project(name="Updated App", status="building")
    patches = _auth_mocks(USER_A_ID)

    with patches[0], patches[1], patches[2], patches[3]:
        with patch(
            "app.api.v1.projects.project_service.update_project",
            new_callable=AsyncMock,
            return_value=updated_project,
        ):
            from app.main import app
            from app.core.database import get_write_session

            mock_session = AsyncMock()

            async def override_write():
                yield mock_session

            app.dependency_overrides[get_write_session] = override_write

            try:
                resp = await client.put(
                    f"/api/v1/projects/{PROJECT_ID}",
                    json={"name": "Updated App", "status": "building"},
                    headers=_auth_headers(),
                )

                assert resp.status_code == 200
                data = resp.json()
                assert data["name"] == "Updated App"
                assert data["status"] == "building"
            finally:
                app.dependency_overrides.pop(get_write_session, None)


# ── DELETE /api/v1/projects/{id} ────────────────────────────────────


@pytest.mark.anyio
async def test_delete_project_success(client: AsyncClient):
    """Delete project returns 204."""
    patches = _auth_mocks(USER_A_ID)

    with patches[0], patches[1], patches[2], patches[3]:
        with patch(
            "app.api.v1.projects.project_service.delete_project",
            new_callable=AsyncMock,
            return_value=None,
        ):
            from app.main import app
            from app.core.database import get_write_session

            mock_session = AsyncMock()

            async def override_write():
                yield mock_session

            app.dependency_overrides[get_write_session] = override_write

            try:
                resp = await client.delete(
                    f"/api/v1/projects/{PROJECT_ID}",
                    headers=_auth_headers(),
                )

                assert resp.status_code == 204
            finally:
                app.dependency_overrides.pop(get_write_session, None)


# ── File operations ──────────────────────────────────────────────────


@pytest.mark.anyio
async def test_get_file_tree(client: AsyncClient):
    """Get file tree returns nested structure."""
    fake_tree = {
        "project_id": PROJECT_ID,
        "tree": [
            {
                "name": "src",
                "path": "src",
                "type": "directory",
                "children": [
                    {
                        "name": "index.tsx",
                        "path": "src/index.tsx",
                        "type": "file",
                        "children": None,
                    }
                ],
            },
            {
                "name": "package.json",
                "path": "package.json",
                "type": "file",
                "children": None,
            },
        ],
    }
    patches = _auth_mocks(USER_A_ID)

    with patches[0], patches[1], patches[2], patches[3]:
        with patch(
            "app.api.v1.projects.project_service.get_file_tree",
            new_callable=AsyncMock,
            return_value=fake_tree,
        ):
            from app.main import app
            from app.core.database import get_read_session

            mock_session = AsyncMock()

            async def override_read():
                yield mock_session

            app.dependency_overrides[get_read_session] = override_read

            try:
                resp = await client.get(
                    f"/api/v1/projects/{PROJECT_ID}/files",
                    headers=_auth_headers(),
                )

                assert resp.status_code == 200
                data = resp.json()
                assert data["project_id"] == PROJECT_ID
                assert len(data["tree"]) == 2
                assert data["tree"][0]["name"] == "src"
                assert data["tree"][0]["type"] == "directory"
                assert len(data["tree"][0]["children"]) == 1
            finally:
                app.dependency_overrides.pop(get_read_session, None)


@pytest.mark.anyio
async def test_get_file_content(client: AsyncClient):
    """Get file content returns file data."""
    patches = _auth_mocks(USER_A_ID)

    with patches[0], patches[1], patches[2], patches[3]:
        with patch(
            "app.api.v1.projects.project_service.get_file_content",
            new_callable=AsyncMock,
            return_value='console.log("hello");',
        ):
            from app.main import app
            from app.core.database import get_read_session

            mock_session = AsyncMock()

            async def override_read():
                yield mock_session

            app.dependency_overrides[get_read_session] = override_read

            try:
                resp = await client.get(
                    f"/api/v1/projects/{PROJECT_ID}/files/content?path=src/index.tsx",
                    headers=_auth_headers(),
                )

                assert resp.status_code == 200
                data = resp.json()
                assert data["project_id"] == PROJECT_ID
                assert data["path"] == "src/index.tsx"
                assert data["content"] == 'console.log("hello");'
            finally:
                app.dependency_overrides.pop(get_read_session, None)


@pytest.mark.anyio
async def test_get_file_content_not_found(client: AsyncClient):
    """Get non-existent file returns 404."""
    from fastapi import HTTPException

    patches = _auth_mocks(USER_A_ID)

    with patches[0], patches[1], patches[2], patches[3]:
        with patch(
            "app.api.v1.projects.project_service.get_file_content",
            new_callable=AsyncMock,
            side_effect=HTTPException(status_code=404, detail="File not found"),
        ):
            from app.main import app
            from app.core.database import get_read_session

            mock_session = AsyncMock()

            async def override_read():
                yield mock_session

            app.dependency_overrides[get_read_session] = override_read

            try:
                resp = await client.get(
                    f"/api/v1/projects/{PROJECT_ID}/files/content?path=nonexistent.txt",
                    headers=_auth_headers(),
                )

                assert resp.status_code == 404
                assert resp.json()["detail"] == "File not found"
            finally:
                app.dependency_overrides.pop(get_read_session, None)


@pytest.mark.anyio
async def test_save_file_content(client: AsyncClient):
    """Save file content returns success message."""
    patches = _auth_mocks(USER_A_ID)

    with patches[0], patches[1], patches[2], patches[3]:
        with patch(
            "app.api.v1.projects.project_service.save_file_content",
            new_callable=AsyncMock,
            return_value=None,
        ):
            from app.main import app
            from app.core.database import get_write_session

            mock_session = AsyncMock()

            async def override_write():
                yield mock_session

            app.dependency_overrides[get_write_session] = override_write

            try:
                resp = await client.put(
                    f"/api/v1/projects/{PROJECT_ID}/files/content",
                    json={
                        "path": "src/index.tsx",
                        "content": 'export default function App() { return <div>Hello</div>; }',
                    },
                    headers=_auth_headers(),
                )

                assert resp.status_code == 200
                assert "saved" in resp.json()["message"].lower()
            finally:
                app.dependency_overrides.pop(get_write_session, None)


@pytest.mark.anyio
async def test_delete_file(client: AsyncClient):
    """Delete file returns success message."""
    patches = _auth_mocks(USER_A_ID)

    with patches[0], patches[1], patches[2], patches[3]:
        with patch(
            "app.api.v1.projects.project_service.delete_file",
            new_callable=AsyncMock,
            return_value=None,
        ):
            from app.main import app
            from app.core.database import get_write_session

            mock_session = AsyncMock()

            async def override_write():
                yield mock_session

            app.dependency_overrides[get_write_session] = override_write

            try:
                resp = await client.delete(
                    f"/api/v1/projects/{PROJECT_ID}/files?path=old-file.txt",
                    headers=_auth_headers(),
                )

                assert resp.status_code == 200
                assert "deleted" in resp.json()["message"].lower()
            finally:
                app.dependency_overrides.pop(get_write_session, None)


@pytest.mark.anyio
async def test_rename_file(client: AsyncClient):
    """Rename file returns success message."""
    patches = _auth_mocks(USER_A_ID)

    with patches[0], patches[1], patches[2], patches[3]:
        with patch(
            "app.api.v1.projects.project_service.rename_file",
            new_callable=AsyncMock,
            return_value=None,
        ):
            from app.main import app
            from app.core.database import get_write_session

            mock_session = AsyncMock()

            async def override_write():
                yield mock_session

            app.dependency_overrides[get_write_session] = override_write

            try:
                resp = await client.post(
                    f"/api/v1/projects/{PROJECT_ID}/files/rename",
                    json={
                        "old_path": "src/old.tsx",
                        "new_path": "src/new.tsx",
                    },
                    headers=_auth_headers(),
                )

                assert resp.status_code == 200
                assert "renamed" in resp.json()["message"].lower()
            finally:
                app.dependency_overrides.pop(get_write_session, None)


@pytest.mark.anyio
async def test_path_traversal_blocked(client: AsyncClient):
    """Attempting path traversal with .. returns 400."""
    from fastapi import HTTPException

    patches = _auth_mocks(USER_A_ID)

    with patches[0], patches[1], patches[2], patches[3]:
        with patch(
            "app.api.v1.projects.project_service.get_file_content",
            new_callable=AsyncMock,
            side_effect=HTTPException(
                status_code=400,
                detail="Invalid file path: path traversal detected",
            ),
        ):
            from app.main import app
            from app.core.database import get_read_session

            mock_session = AsyncMock()

            async def override_read():
                yield mock_session

            app.dependency_overrides[get_read_session] = override_read

            try:
                resp = await client.get(
                    f"/api/v1/projects/{PROJECT_ID}/files/content?path=../../etc/passwd",
                    headers=_auth_headers(),
                )

                assert resp.status_code == 400
                assert "traversal" in resp.json()["detail"].lower()
            finally:
                app.dependency_overrides.pop(get_read_session, None)


# ── Service-level unit tests ────────────────────────────────────────


@pytest.mark.anyio
async def test_service_create_project():
    """Service creates project with correct attributes."""
    mock_session = AsyncMock()
    mock_session.add = MagicMock()
    mock_session.flush = AsyncMock()

    # Make refresh populate the project object
    async def fake_refresh(obj):
        # Project object already has attributes from constructor
        pass

    mock_session.refresh = AsyncMock(side_effect=fake_refresh)

    from app.services.project_service import create_project

    project = await create_project(
        user_id=uuid.UUID(USER_A_ID),
        name="Test Project",
        description="A desc",
        framework="nextjs",
        session=mock_session,
    )

    assert project.name == "Test Project"
    assert project.description == "A desc"
    assert project.user_id == uuid.UUID(USER_A_ID)
    mock_session.add.assert_called_once()
    mock_session.flush.assert_called_once()


@pytest.mark.anyio
async def test_service_create_project_invalid_framework():
    """Service rejects invalid framework."""
    from fastapi import HTTPException

    from app.services.project_service import create_project

    mock_session = AsyncMock()

    with pytest.raises(HTTPException) as exc_info:
        await create_project(
            user_id=uuid.UUID(USER_A_ID),
            name="Test",
            description=None,
            framework="invalid_fw",
            session=mock_session,
        )

    assert exc_info.value.status_code == 400
    assert "Invalid framework" in exc_info.value.detail


@pytest.mark.anyio
async def test_service_get_project_ownership():
    """Service returns 404 when project doesn't belong to user."""
    from fastapi import HTTPException

    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_session.execute = AsyncMock(return_value=mock_result)

    from app.services.project_service import get_project

    with pytest.raises(HTTPException) as exc_info:
        await get_project(
            project_id=uuid.UUID(PROJECT_ID),
            user_id=uuid.UUID(USER_B_ID),
            session=mock_session,
        )

    # Must be 404 — never reveal that the project exists
    assert exc_info.value.status_code == 404


@pytest.mark.anyio
async def test_service_file_tree():
    """Service builds correct nested tree from R2 keys."""
    from app.services.project_service import get_file_tree

    pid = uuid.UUID(PROJECT_ID)
    uid = uuid.UUID(USER_A_ID)
    prefix = f"projects/{pid}/files/"

    # Mock session for ownership check
    mock_session = AsyncMock()
    mock_result = MagicMock()
    fake_project = _make_fake_project()
    mock_result.scalar_one_or_none.return_value = fake_project
    mock_session.execute = AsyncMock(return_value=mock_result)

    # Mock R2 list_files
    r2_keys = [
        f"{prefix}package.json",
        f"{prefix}src/App.tsx",
        f"{prefix}src/index.tsx",
        f"{prefix}src/components/Button.tsx",
    ]

    with patch(
        "app.services.project_service.storage_service.list_files",
        new_callable=AsyncMock,
        return_value=r2_keys,
    ):
        result = await get_file_tree(pid, uid, mock_session)

    assert result["project_id"] == str(pid)
    tree = result["tree"]

    # Should have package.json and src directory
    names = {node["name"] for node in tree}
    assert "package.json" in names
    assert "src" in names

    # src should have App.tsx, index.tsx, and components/
    src = next(n for n in tree if n["name"] == "src")
    assert src["type"] == "directory"
    src_names = {c["name"] for c in src["children"]}
    assert "App.tsx" in src_names
    assert "index.tsx" in src_names
    assert "components" in src_names


@pytest.mark.anyio
async def test_service_save_and_read_file():
    """Service correctly saves and reads file content via R2."""
    from app.services.project_service import save_file_content, get_file_content

    pid = uuid.UUID(PROJECT_ID)
    uid = uuid.UUID(USER_A_ID)

    # Mock session for ownership check
    mock_session = AsyncMock()
    mock_result = MagicMock()
    fake_project = _make_fake_project()
    mock_result.scalar_one_or_none.return_value = fake_project
    mock_session.execute = AsyncMock(return_value=mock_result)

    file_content = 'export const hello = "world";'

    with patch(
        "app.services.project_service.storage_service.upload_file",
        new_callable=AsyncMock,
        return_value=f"projects/{pid}/files/src/hello.ts",
    ) as mock_upload:
        await save_file_content(pid, uid, "src/hello.ts", file_content, mock_session)

        mock_upload.assert_called_once()
        call_kwargs = mock_upload.call_args
        assert call_kwargs.kwargs["content"] == file_content.encode("utf-8")
        assert call_kwargs.kwargs["content_type"] == "text/typescript"

    with patch(
        "app.services.project_service.storage_service.download_file",
        new_callable=AsyncMock,
        return_value=file_content.encode("utf-8"),
    ):
        content = await get_file_content(pid, uid, "src/hello.ts", mock_session)
        assert content == file_content


@pytest.mark.anyio
async def test_service_delete_project_cleans_r2():
    """Deleting a project also deletes R2 files."""
    from app.services.project_service import delete_project

    pid = uuid.UUID(PROJECT_ID)
    uid = uuid.UUID(USER_A_ID)

    mock_session = AsyncMock()
    mock_result = MagicMock()
    fake_project = _make_fake_project()
    mock_result.scalar_one_or_none.return_value = fake_project
    mock_session.execute = AsyncMock(return_value=mock_result)
    mock_session.delete = AsyncMock()
    mock_session.flush = AsyncMock()

    with patch(
        "app.services.project_service.storage_service.delete_prefix",
        new_callable=AsyncMock,
        return_value=5,
    ) as mock_delete_prefix:
        await delete_project(pid, uid, mock_session)

        # Verify R2 cleanup was called
        mock_delete_prefix.assert_called_once_with(f"projects/{pid}/files/")

        # Verify DB deletion
        mock_session.delete.assert_called_once_with(fake_project)
        mock_session.flush.assert_called_once()


@pytest.mark.anyio
async def test_service_path_sanitization():
    """Path sanitization blocks traversal attempts."""
    from fastapi import HTTPException

    from app.services.project_service import _sanitize_path

    # ── Normal paths should pass ──
    assert _sanitize_path("src/index.tsx") == "src/index.tsx"
    assert _sanitize_path("/src/index.tsx") == "src/index.tsx"
    assert _sanitize_path("package.json") == "package.json"
    assert _sanitize_path("src/components/Button.tsx") == "src/components/Button.tsx"

    # Filenames containing '..' as a substring (not a component) are fine
    assert _sanitize_path("file..name.txt") == "file..name.txt"

    # ── Path normalization (collapse ./ and //) ──
    assert _sanitize_path("src/./index.tsx") == "src/index.tsx"
    assert _sanitize_path("src//index.tsx") == "src/index.tsx"

    # ── Directory traversal should be blocked ──
    with pytest.raises(HTTPException) as exc_info:
        _sanitize_path("../../../etc/passwd")
    assert exc_info.value.status_code == 400

    with pytest.raises(HTTPException) as exc_info:
        _sanitize_path("src/../../secrets")
    assert exc_info.value.status_code == 400

    # Sneaky traversal via dot-collapse
    with pytest.raises(HTTPException) as exc_info:
        _sanitize_path("src/foo/../../..")
    assert exc_info.value.status_code == 400

    # ── Null bytes should be blocked ──
    with pytest.raises(HTTPException) as exc_info:
        _sanitize_path("src/index.tsx\x00../../etc/passwd")
    assert exc_info.value.status_code == 400
    assert "null" in exc_info.value.detail.lower()

    # ── Backslash traversal should be blocked ──
    with pytest.raises(HTTPException) as exc_info:
        _sanitize_path("src\\..\\..\\etc\\passwd")
    assert exc_info.value.status_code == 400
    assert "backslash" in exc_info.value.detail.lower()

    # ── Empty / root-only path should be blocked ──
    with pytest.raises(HTTPException) as exc_info:
        _sanitize_path("")
    # Empty string has min_length=1 at the API layer,
    # but the service also rejects it
    assert exc_info.value.status_code == 400

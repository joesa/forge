"""
Tests for the FORGE preview system backend.

Covers:
  1. Preview URL lookup
  2. Health check with Redis caching
  3. Screenshot capture (mocked Playwright + R2)
  4. Share token creation (HMAC + Redis + DB)
  5. Share revocation (ownership enforcement, 403 for non-owner)
  6. Build snapshots (capture + list)
  7. Annotations (CRUD, validate coordinates, resolve, clear, AI context)
  8. File sync (Redis PUBLISH)
  9. Cross-user access control
  10. Console WebSocket (connection test)

All tests mock external services — never call real APIs (AGENTS.md rule #7).
"""

import datetime
import hashlib
import hmac
import json
import sys
import time
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.config import settings
from app.models.annotation import Annotation
from app.models.build import Build, BuildStatus
from app.models.build_snapshot import BuildSnapshot
from app.models.preview_share import PreviewShare
from app.models.sandbox import Sandbox, SandboxStatus
from app.schemas.preview import (
    AnnotationCreateRequest,
    HealthResult,
    PreviewURLResult,
    ScreenshotResult,
    ShareResult,
    SnapshotResponse,
)
from app.services import (
    annotation_service,
    file_sync_service,
    preview_service,
    snapshot_service,
)


# ── Helpers ──────────────────────────────────────────────────────────

USER_A_ID = str(uuid.uuid4())
USER_B_ID = str(uuid.uuid4())
SANDBOX_ID = str(uuid.uuid4())
PROJECT_ID = str(uuid.uuid4())
BUILD_ID = str(uuid.uuid4())


def _make_sandbox(
    sandbox_id: str = SANDBOX_ID,
    user_id: str = USER_A_ID,
    status: SandboxStatus = SandboxStatus.assigned,
) -> MagicMock:
    """Create a mock Sandbox ORM object."""
    sandbox = MagicMock(spec=Sandbox)
    sandbox.id = uuid.UUID(sandbox_id)
    sandbox.user_id = uuid.UUID(user_id)
    sandbox.project_id = uuid.UUID(PROJECT_ID)
    sandbox.status = status
    sandbox.vm_url = f"https://{sandbox_id}.preview.forge.dev"
    sandbox.last_heartbeat = datetime.datetime.now(datetime.timezone.utc)
    sandbox.assigned_at = datetime.datetime.now(datetime.timezone.utc)
    sandbox.created_at = datetime.datetime.now(datetime.timezone.utc)
    sandbox.updated_at = datetime.datetime.now(datetime.timezone.utc)
    return sandbox


def _make_annotation(
    project_id: str = PROJECT_ID,
    user_id: str = USER_A_ID,
    route: str = "/dashboard",
    css_selector: str = ".btn-primary",
    comment: str = "Button too small",
    x_pct: float = 0.5,
    y_pct: float = 0.3,
    resolved: bool = False,
) -> MagicMock:
    """Create a mock Annotation ORM object."""
    ann = MagicMock(spec=Annotation)
    ann.id = uuid.uuid4()
    ann.project_id = uuid.UUID(project_id)
    ann.user_id = uuid.UUID(user_id)
    ann.page_route = route
    ann.css_selector = css_selector
    ann.session_id = "session-123"
    ann.content = comment
    ann.x_pct = x_pct
    ann.y_pct = y_pct
    ann.resolved = resolved
    ann.created_at = datetime.datetime.now(datetime.timezone.utc)
    ann.updated_at = datetime.datetime.now(datetime.timezone.utc)
    return ann


def _make_snapshot(
    build_id: str = BUILD_ID,
    project_id: str = PROJECT_ID,
    agent_number: int = 1,
    agent_type: str = "layout_agent",
) -> MagicMock:
    """Create a mock BuildSnapshot ORM object."""
    snap = MagicMock(spec=BuildSnapshot)
    snap.id = uuid.uuid4()
    snap.build_id = uuid.UUID(build_id)
    snap.project_id = uuid.UUID(project_id)
    snap.snapshot_index = agent_number
    snap.label = agent_type
    snap.screenshot_url = f"https://r2.example.com/snapshots/{project_id}/{build_id}/{agent_number:02d}_{agent_type}.webp"
    snap.created_at = datetime.datetime.now(datetime.timezone.utc)
    snap.updated_at = datetime.datetime.now(datetime.timezone.utc)
    return snap


# ══════════════════════════════════════════════════════════════════════
# 1. PREVIEW URL
# ══════════════════════════════════════════════════════════════════════


class TestPreviewURL:
    """Tests for preview_service.get_preview_url."""

    @pytest.mark.asyncio
    async def test_returns_correct_url(self) -> None:
        """Preview URL follows the pattern: https://{sandbox_id}.preview.forge.dev"""
        sandbox = _make_sandbox()

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sandbox
        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await preview_service.get_preview_url(
            sandbox_id=SANDBOX_ID,
            user_id=USER_A_ID,
            session=mock_session,
        )

        assert isinstance(result, PreviewURLResult)
        assert SANDBOX_ID in result.url
        assert settings.PREVIEW_DOMAIN in result.url
        assert result.ready is True

    @pytest.mark.asyncio
    async def test_not_ready_when_warming(self) -> None:
        """Sandbox in 'warming' status should not be ready."""
        sandbox = _make_sandbox(status=SandboxStatus.warming)

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sandbox
        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await preview_service.get_preview_url(
            sandbox_id=SANDBOX_ID,
            user_id=USER_A_ID,
            session=mock_session,
        )

        assert result.ready is False

    @pytest.mark.asyncio
    async def test_lookup_error_when_not_found(self) -> None:
        """Should raise LookupError when sandbox not found."""
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)

        with pytest.raises(LookupError, match="not found"):
            await preview_service.get_preview_url(
                sandbox_id=SANDBOX_ID,
                user_id=USER_A_ID,
                session=mock_session,
            )

    @pytest.mark.asyncio
    async def test_expires_at_calculated(self) -> None:
        """expires_at should be 24h after last_heartbeat."""
        sandbox = _make_sandbox()
        heartbeat = datetime.datetime(
            2026, 1, 1, 12, 0, 0, tzinfo=datetime.timezone.utc
        )
        sandbox.last_heartbeat = heartbeat

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sandbox
        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await preview_service.get_preview_url(
            sandbox_id=SANDBOX_ID,
            user_id=USER_A_ID,
            session=mock_session,
        )

        expected = heartbeat + datetime.timedelta(hours=24)
        assert result.expires_at == expected


# ══════════════════════════════════════════════════════════════════════
# 2. HEALTH CHECK
# ══════════════════════════════════════════════════════════════════════


class TestPreviewHealth:
    """Tests for preview_service.check_preview_health."""

    @pytest.mark.asyncio
    @patch("app.services.preview_service.get_cache")
    @patch("app.services.preview_service.set_cache")
    @patch("httpx.AsyncClient")
    async def test_healthy_sandbox(
        self,
        mock_client_class: MagicMock,
        mock_set_cache: AsyncMock,
        mock_get_cache: AsyncMock,
    ) -> None:
        """Healthy sandbox returns healthy=True with latency."""
        mock_get_cache.return_value = None  # No cache hit

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_class.return_value = mock_client

        result = await preview_service.check_preview_health(SANDBOX_ID)

        assert isinstance(result, HealthResult)
        assert result.healthy is True
        assert result.latency_ms >= 0
        mock_set_cache.assert_called_once()

    @pytest.mark.asyncio
    @patch("app.services.preview_service.get_cache")
    async def test_cached_result(self, mock_get_cache: AsyncMock) -> None:
        """Should return cached result without making HTTP request."""
        cached_data = json.dumps({
            "healthy": True,
            "latency_ms": 42,
            "last_checked": datetime.datetime.now(
                datetime.timezone.utc
            ).isoformat(),
        })
        mock_get_cache.return_value = cached_data

        result = await preview_service.check_preview_health(SANDBOX_ID)

        assert result.healthy is True
        assert result.latency_ms == 42

    @pytest.mark.asyncio
    @patch("app.services.preview_service.get_cache")
    @patch("app.services.preview_service.set_cache")
    @patch("httpx.AsyncClient")
    async def test_unhealthy_sandbox(
        self,
        mock_client_class: MagicMock,
        mock_set_cache: AsyncMock,
        mock_get_cache: AsyncMock,
    ) -> None:
        """Unreachable sandbox returns healthy=False."""
        mock_get_cache.return_value = None

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=Exception("Connection refused"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_class.return_value = mock_client

        result = await preview_service.check_preview_health(SANDBOX_ID)

        assert result.healthy is False


# ══════════════════════════════════════════════════════════════════════
# 3. SCREENSHOT
# ══════════════════════════════════════════════════════════════════════


class TestScreenshot:
    """Tests for preview_service.take_screenshot."""

    @pytest.mark.asyncio
    @patch("app.services.preview_service.storage_service")
    async def test_screenshot_capture(
        self, mock_storage: MagicMock
    ) -> None:
        """Screenshot should call Playwright, upload to R2, return URL."""
        mock_storage.upload_file = AsyncMock(return_value="key")
        mock_storage.generate_presigned_url = AsyncMock(
            return_value="https://r2.example.com/screenshot.webp"
        )

        # Mock Playwright
        mock_page = AsyncMock()
        mock_page.goto = AsyncMock()
        mock_page.screenshot = AsyncMock(return_value=b"fake-screenshot-bytes")

        mock_browser = AsyncMock()
        mock_browser.new_page = AsyncMock(return_value=mock_page)
        mock_browser.close = AsyncMock()

        mock_chromium = AsyncMock()
        mock_chromium.launch = AsyncMock(return_value=mock_browser)

        mock_pw = AsyncMock()
        mock_pw.chromium = mock_chromium
        mock_pw.__aenter__ = AsyncMock(return_value=mock_pw)
        mock_pw.__aexit__ = AsyncMock(return_value=None)

        # Create a fake playwright module since it's not installed
        mock_playwright_module = MagicMock()
        mock_playwright_module.async_playwright = MagicMock(return_value=mock_pw)

        with patch.dict(sys.modules, {
            "playwright": MagicMock(),
            "playwright.async_api": mock_playwright_module,
        }):
            result = await preview_service.take_screenshot(
                sandbox_id=SANDBOX_ID,
                route="/dashboard",
                width=1280,
                height=800,
            )

        assert isinstance(result, ScreenshotResult)
        assert "r2.example.com" in result.screenshot_url
        mock_storage.upload_file.assert_called_once()

    @pytest.mark.asyncio
    async def test_slugify_route(self) -> None:
        """Route slugification produces safe filenames."""
        assert preview_service._slugify_route("/") == "root"
        assert preview_service._slugify_route("/dashboard") == "dashboard"
        assert preview_service._slugify_route("/users/profile") == "users_profile"
        assert preview_service._slugify_route("/page?q=test") == "pageqtest"


# ══════════════════════════════════════════════════════════════════════
# 4. SHARE CREATION
# ══════════════════════════════════════════════════════════════════════


class TestShareCreation:
    """Tests for preview_service.create_share."""

    @pytest.mark.asyncio
    @patch("app.services.preview_service.set_cache")
    async def test_share_token_format(
        self, mock_set_cache: AsyncMock
    ) -> None:
        """Share token is HMAC-SHA256 hex digest."""
        sandbox = _make_sandbox()

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sandbox
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.add = MagicMock()
        mock_session.flush = AsyncMock()

        result = await preview_service.create_share(
            sandbox_id=SANDBOX_ID,
            user_id=USER_A_ID,
            expires_hours=24,
            session=mock_session,
        )

        assert isinstance(result, ShareResult)
        # Token should be a hex string (64 chars for SHA-256)
        assert len(result.token) == 64
        assert all(c in "0123456789abcdef" for c in result.token)

    @pytest.mark.asyncio
    @patch("app.services.preview_service.set_cache")
    async def test_share_url_format(
        self, mock_set_cache: AsyncMock
    ) -> None:
        """Share URL includes sandbox_id and token."""
        sandbox = _make_sandbox()

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sandbox
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.add = MagicMock()
        mock_session.flush = AsyncMock()

        result = await preview_service.create_share(
            sandbox_id=SANDBOX_ID,
            user_id=USER_A_ID,
            expires_hours=24,
            session=mock_session,
        )

        assert SANDBOX_ID in result.share_url
        assert result.token in result.share_url
        assert settings.PREVIEW_DOMAIN in result.share_url

    @pytest.mark.asyncio
    @patch("app.services.preview_service.set_cache")
    async def test_share_redis_cache(
        self, mock_set_cache: AsyncMock
    ) -> None:
        """Share data should be cached in Redis with TTL."""
        sandbox = _make_sandbox()

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sandbox
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.add = MagicMock()
        mock_session.flush = AsyncMock()

        await preview_service.create_share(
            sandbox_id=SANDBOX_ID,
            user_id=USER_A_ID,
            expires_hours=12,
            session=mock_session,
        )

        # Check Redis was called with correct TTL
        mock_set_cache.assert_called_once()
        call_args = mock_set_cache.call_args
        assert call_args[0][2] == 12 * 3600  # TTL = 12 hours in seconds

    @pytest.mark.asyncio
    @patch("app.services.preview_service.set_cache")
    async def test_share_expires_at(
        self, mock_set_cache: AsyncMock
    ) -> None:
        """Share should expire at the correct time."""
        sandbox = _make_sandbox()

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sandbox
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.add = MagicMock()
        mock_session.flush = AsyncMock()

        before = datetime.datetime.now(datetime.timezone.utc)
        result = await preview_service.create_share(
            sandbox_id=SANDBOX_ID,
            user_id=USER_A_ID,
            expires_hours=24,
            session=mock_session,
        )
        after = datetime.datetime.now(datetime.timezone.utc)

        # expires_at should be ~24h from now
        expected_min = before + datetime.timedelta(hours=24)
        expected_max = after + datetime.timedelta(hours=24)
        assert expected_min <= result.expires_at <= expected_max

    def test_hmac_token_generation(self) -> None:
        """HMAC token is deterministic for the same inputs."""
        token1 = preview_service._generate_share_token("sandbox-123", 1000000)
        token2 = preview_service._generate_share_token("sandbox-123", 1000000)
        assert token1 == token2

        # Different inputs produce different tokens
        token3 = preview_service._generate_share_token("sandbox-456", 1000000)
        assert token1 != token3


# ══════════════════════════════════════════════════════════════════════
# 5. SHARE REVOCATION (with cross-user check)
# ══════════════════════════════════════════════════════════════════════


class TestShareRevocation:
    """Tests for preview_service.revoke_share."""

    @pytest.mark.asyncio
    @patch("app.services.preview_service.delete_cache")
    @patch("app.services.preview_service.get_cache")
    async def test_owner_can_revoke(
        self,
        mock_get_cache: AsyncMock,
        mock_delete_cache: AsyncMock,
    ) -> None:
        """Owner should be able to revoke their own share."""
        token = "abc123def456"
        mock_get_cache.return_value = json.dumps({
            "sandbox_id": SANDBOX_ID,
            "expires_at": datetime.datetime.now(
                datetime.timezone.utc
            ).isoformat(),
            "user_id": USER_A_ID,
        })

        mock_session = AsyncMock()
        mock_result = MagicMock()
        share = MagicMock(spec=PreviewShare)
        share.user_id = uuid.UUID(USER_A_ID)
        mock_result.scalar_one_or_none.return_value = share
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.delete = AsyncMock()
        mock_session.flush = AsyncMock()

        result = await preview_service.revoke_share(
            token=token,
            user_id=USER_A_ID,
            session=mock_session,
        )

        assert result is True
        mock_delete_cache.assert_called_once()

    @pytest.mark.asyncio
    @patch("app.services.preview_service.get_cache")
    async def test_non_owner_gets_403(
        self, mock_get_cache: AsyncMock
    ) -> None:
        """User B cannot revoke User A's share link (must raise PermissionError)."""
        token = "abc123def456"
        mock_get_cache.return_value = json.dumps({
            "sandbox_id": SANDBOX_ID,
            "expires_at": datetime.datetime.now(
                datetime.timezone.utc
            ).isoformat(),
            "user_id": USER_A_ID,  # Owned by User A
        })

        mock_session = AsyncMock()

        with pytest.raises(PermissionError, match="do not own"):
            await preview_service.revoke_share(
                token=token,
                user_id=USER_B_ID,  # User B trying to revoke
                session=mock_session,
            )

    @pytest.mark.asyncio
    @patch("app.services.preview_service.delete_cache")
    @patch("app.services.preview_service.get_cache")
    async def test_revoke_no_redis_cache_but_db_record(
        self,
        mock_get_cache: AsyncMock,
        mock_delete_cache: AsyncMock,
    ) -> None:
        """Even if Redis cache expired, should check DB and still revoke."""
        token = "expired-redis-token"
        mock_get_cache.return_value = None  # Redis cache expired

        mock_session = AsyncMock()
        mock_result = MagicMock()
        share = MagicMock(spec=PreviewShare)
        share.user_id = uuid.UUID(USER_A_ID)
        mock_result.scalar_one_or_none.return_value = share
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.delete = AsyncMock()
        mock_session.flush = AsyncMock()

        result = await preview_service.revoke_share(
            token=token,
            user_id=USER_A_ID,
            session=mock_session,
        )

        assert result is True

    @pytest.mark.asyncio
    @patch("app.services.preview_service.delete_cache")
    @patch("app.services.preview_service.get_cache")
    async def test_revoke_non_owner_db_check(
        self,
        mock_get_cache: AsyncMock,
        mock_delete_cache: AsyncMock,
    ) -> None:
        """Non-owner blocked even when Redis cache is empty (DB check)."""
        token = "some-token"
        mock_get_cache.return_value = None  # No Redis cache

        mock_session = AsyncMock()
        mock_result = MagicMock()
        share = MagicMock(spec=PreviewShare)
        share.user_id = uuid.UUID(USER_A_ID)  # Owned by User A
        mock_result.scalar_one_or_none.return_value = share
        mock_session.execute = AsyncMock(return_value=mock_result)

        with pytest.raises(PermissionError, match="do not own"):
            await preview_service.revoke_share(
                token=token,
                user_id=USER_B_ID,  # User B trying
                session=mock_session,
            )


# ══════════════════════════════════════════════════════════════════════
# 6. SNAPSHOTS
# ══════════════════════════════════════════════════════════════════════


class TestSnapshots:
    """Tests for snapshot_service."""

    @pytest.mark.asyncio
    @patch("app.services.snapshot_service.publish_event")
    @patch("app.services.snapshot_service.storage_service")
    async def test_capture_snapshot(
        self,
        mock_storage: MagicMock,
        mock_publish: AsyncMock,
    ) -> None:
        """Capture should: Playwright → R2 → DB → Redis PUBLISH."""
        mock_storage.upload_file = AsyncMock(return_value="key")
        mock_storage.generate_presigned_url = AsyncMock(
            return_value="https://r2.example.com/snapshot.webp"
        )

        # Mock Playwright
        mock_page = AsyncMock()
        mock_page.goto = AsyncMock()
        mock_page.wait_for_function = AsyncMock()
        mock_page.screenshot = AsyncMock(return_value=b"fake-screenshot")

        mock_browser = AsyncMock()
        mock_browser.new_page = AsyncMock(return_value=mock_page)
        mock_browser.close = AsyncMock()

        mock_chromium = AsyncMock()
        mock_chromium.launch = AsyncMock(return_value=mock_browser)

        mock_pw = AsyncMock()
        mock_pw.chromium = mock_chromium
        mock_pw.__aenter__ = AsyncMock(return_value=mock_pw)
        mock_pw.__aexit__ = AsyncMock(return_value=None)

        mock_session = AsyncMock()
        mock_session.add = MagicMock()
        mock_session.flush = AsyncMock()

        # Create a fake playwright module since it's not installed
        mock_playwright_module = MagicMock()
        mock_playwright_module.async_playwright = MagicMock(return_value=mock_pw)

        with patch.dict(sys.modules, {
            "playwright": MagicMock(),
            "playwright.async_api": mock_playwright_module,
        }):
            result = await snapshot_service.capture_snapshot(
                build_id=BUILD_ID,
                project_id=PROJECT_ID,
                agent_type="layout_agent",
                agent_number=3,
                session=mock_session,
            )

        assert isinstance(result, BuildSnapshot)
        mock_storage.upload_file.assert_called_once()
        mock_publish.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_snapshots_by_build(self) -> None:
        """Get snapshots for a specific build, ordered by agent_number."""
        snap1 = _make_snapshot(agent_number=1, agent_type="layout")
        snap2 = _make_snapshot(agent_number=2, agent_type="style")

        # Mock ownership check (first call) + snapshots query (second call)
        mock_project = MagicMock()
        mock_project.id = uuid.UUID(PROJECT_ID)
        mock_project.user_id = uuid.UUID(USER_A_ID)

        mock_ownership_result = MagicMock()
        mock_ownership_result.scalar_one_or_none.return_value = mock_project

        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [snap1, snap2]
        mock_snap_result = MagicMock()
        mock_snap_result.scalars.return_value = mock_scalars

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(
            side_effect=[mock_ownership_result, mock_snap_result]
        )

        results = await snapshot_service.get_snapshots(
            project_id=PROJECT_ID,
            user_id=USER_A_ID,
            build_id=BUILD_ID,
            session=mock_session,
        )

        assert len(results) == 2

    @pytest.mark.asyncio
    async def test_get_snapshots_latest_build(self) -> None:
        """Without build_id, get snapshots for the latest completed build."""
        # Mock ownership check (first) + latest build (second) + snapshots (third)
        mock_project = MagicMock()
        mock_project.id = uuid.UUID(PROJECT_ID)
        mock_project.user_id = uuid.UUID(USER_A_ID)

        mock_ownership_result = MagicMock()
        mock_ownership_result.scalar_one_or_none.return_value = mock_project

        mock_build_result = MagicMock()
        mock_build_result.scalar_one_or_none.return_value = uuid.UUID(BUILD_ID)

        snap = _make_snapshot()
        mock_snap_scalars = MagicMock()
        mock_snap_scalars.all.return_value = [snap]
        mock_snap_result = MagicMock()
        mock_snap_result.scalars.return_value = mock_snap_scalars

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(
            side_effect=[mock_ownership_result, mock_build_result, mock_snap_result]
        )

        results = await snapshot_service.get_snapshots(
            project_id=PROJECT_ID,
            user_id=USER_A_ID,
            build_id=None,
            session=mock_session,
        )

        assert len(results) == 1

    @pytest.mark.asyncio
    async def test_get_snapshots_no_builds(self) -> None:
        """No completed builds returns empty list."""
        # Mock ownership check (first) + latest build query returns None (second)
        mock_project = MagicMock()
        mock_project.id = uuid.UUID(PROJECT_ID)
        mock_project.user_id = uuid.UUID(USER_A_ID)

        mock_ownership_result = MagicMock()
        mock_ownership_result.scalar_one_or_none.return_value = mock_project

        mock_build_result = MagicMock()
        mock_build_result.scalar_one_or_none.return_value = None

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(
            side_effect=[mock_ownership_result, mock_build_result]
        )

        results = await snapshot_service.get_snapshots(
            project_id=PROJECT_ID,
            user_id=USER_A_ID,
            build_id=None,
            session=mock_session,
        )

        assert results == []


# ══════════════════════════════════════════════════════════════════════
# 7. ANNOTATIONS
# ══════════════════════════════════════════════════════════════════════


class TestAnnotations:
    """Tests for annotation_service."""

    def _mock_session_with_project(
        self, user_id: str = USER_A_ID
    ) -> AsyncMock:
        """Create a mock session that returns a project owned by user_id."""
        mock_session = AsyncMock()
        mock_project = MagicMock()
        mock_project.id = uuid.UUID(PROJECT_ID)
        mock_project.user_id = uuid.UUID(user_id)

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_project
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.add = MagicMock()
        mock_session.flush = AsyncMock()
        return mock_session

    @pytest.mark.asyncio
    @patch("app.services.annotation_service.publish_event")
    async def test_create_annotation(
        self, mock_publish: AsyncMock
    ) -> None:
        """Create annotation with valid coordinates."""
        mock_session = self._mock_session_with_project()

        result = await annotation_service.create_annotation(
            project_id=PROJECT_ID,
            user_id=USER_A_ID,
            session_id="session-123",
            css_selector=".btn-primary",
            route="/dashboard",
            comment="Button too small",
            x_pct=0.5,
            y_pct=0.3,
            session=mock_session,
        )

        assert isinstance(result, Annotation)
        mock_session.add.assert_called_once()
        mock_publish.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_annotation_invalid_coordinates(self) -> None:
        """Coordinates outside [0.0, 1.0] should raise ValueError."""
        mock_session = self._mock_session_with_project()

        with pytest.raises(ValueError, match="between 0.0 and 1.0"):
            await annotation_service.create_annotation(
                project_id=PROJECT_ID,
                user_id=USER_A_ID,
                session_id="session-123",
                css_selector=".btn",
                route="/",
                comment="Test",
                x_pct=1.5,  # Invalid
                y_pct=0.3,
                session=mock_session,
            )

    @pytest.mark.asyncio
    async def test_create_annotation_project_not_found(self) -> None:
        """Should raise LookupError if project not found or not owned."""
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)

        with pytest.raises(LookupError, match="not found"):
            await annotation_service.create_annotation(
                project_id=PROJECT_ID,
                user_id=USER_A_ID,
                session_id="session-123",
                css_selector=".btn",
                route="/",
                comment="Test",
                x_pct=0.5,
                y_pct=0.3,
                session=mock_session,
            )

    @pytest.mark.asyncio
    async def test_get_annotations_unresolved_only(self) -> None:
        """Default: return only unresolved annotations."""
        ann = _make_annotation(resolved=False)

        # Mock ownership check (first) + annotations query (second)
        mock_project = MagicMock()
        mock_project.id = uuid.UUID(PROJECT_ID)
        mock_project.user_id = uuid.UUID(USER_A_ID)

        mock_ownership_result = MagicMock()
        mock_ownership_result.scalar_one_or_none.return_value = mock_project

        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [ann]
        mock_ann_result = MagicMock()
        mock_ann_result.scalars.return_value = mock_scalars

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(
            side_effect=[mock_ownership_result, mock_ann_result]
        )

        results = await annotation_service.get_annotations(
            project_id=PROJECT_ID,
            user_id=USER_A_ID,
            include_resolved=False,
            session=mock_session,
        )

        assert len(results) == 1

    @pytest.mark.asyncio
    async def test_resolve_annotation(self) -> None:
        """Resolve sets resolved=True."""
        ann = _make_annotation()
        ann.project_id = uuid.UUID(PROJECT_ID)
        ann.resolved = False

        mock_project = MagicMock()
        mock_project.id = uuid.UUID(PROJECT_ID)
        mock_project.user_id = uuid.UUID(USER_A_ID)

        mock_session = AsyncMock()

        # First execute: annotation lookup
        mock_ann_result = MagicMock()
        mock_ann_result.scalar_one_or_none.return_value = ann
        # Second execute: project ownership check
        mock_proj_result = MagicMock()
        mock_proj_result.scalar_one_or_none.return_value = mock_project

        mock_session.execute = AsyncMock(
            side_effect=[mock_ann_result, mock_proj_result]
        )
        mock_session.flush = AsyncMock()

        result = await annotation_service.resolve_annotation(
            annotation_id=str(ann.id),
            user_id=USER_A_ID,
            session=mock_session,
        )

        assert result.resolved is True

    @pytest.mark.asyncio
    async def test_delete_annotation(self) -> None:
        """Delete removes annotation from DB."""
        ann = _make_annotation()
        ann.project_id = uuid.UUID(PROJECT_ID)

        mock_project = MagicMock()
        mock_project.id = uuid.UUID(PROJECT_ID)
        mock_project.user_id = uuid.UUID(USER_A_ID)

        mock_session = AsyncMock()
        mock_ann_result = MagicMock()
        mock_ann_result.scalar_one_or_none.return_value = ann
        mock_proj_result = MagicMock()
        mock_proj_result.scalar_one_or_none.return_value = mock_project

        mock_session.execute = AsyncMock(
            side_effect=[mock_ann_result, mock_proj_result]
        )
        mock_session.delete = AsyncMock()
        mock_session.flush = AsyncMock()

        result = await annotation_service.delete_annotation(
            annotation_id=str(ann.id),
            user_id=USER_A_ID,
            session=mock_session,
        )

        assert result is True
        mock_session.delete.assert_called_once()

    @pytest.mark.asyncio
    async def test_clear_annotations(self) -> None:
        """Clear removes all annotations for a project."""
        mock_project = MagicMock()
        mock_project.id = uuid.UUID(PROJECT_ID)
        mock_project.user_id = uuid.UUID(USER_A_ID)

        mock_session = AsyncMock()

        # First execute: project ownership
        mock_proj_result = MagicMock()
        mock_proj_result.scalar_one_or_none.return_value = mock_project
        # Second execute: delete returning IDs
        mock_del_scalars = MagicMock()
        mock_del_scalars.all.return_value = [uuid.uuid4(), uuid.uuid4(), uuid.uuid4()]
        mock_del_result = MagicMock()
        mock_del_result.scalars.return_value = mock_del_scalars

        mock_session.execute = AsyncMock(
            side_effect=[mock_proj_result, mock_del_result]
        )
        mock_session.flush = AsyncMock()

        count = await annotation_service.clear_annotations(
            project_id=PROJECT_ID,
            user_id=USER_A_ID,
            session=mock_session,
        )

        assert count == 3

    @pytest.mark.asyncio
    async def test_ai_context_formatting(self) -> None:
        """AI context returns properly formatted string."""
        ann1 = _make_annotation(
            route="/dashboard",
            css_selector=".btn-primary",
            comment="Button too small",
        )
        ann2 = _make_annotation(
            route="/settings",
            css_selector="#save-btn",
            comment="Missing hover state",
        )

        mock_session = AsyncMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [ann1, ann2]
        mock_result = MagicMock()
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute = AsyncMock(return_value=mock_result)

        context = await annotation_service.get_annotations_for_ai_context(
            project_id=PROJECT_ID,
            session=mock_session,
        )

        assert "The user has flagged these UI issues:" in context
        assert "[/dashboard]" in context
        assert ".btn-primary" in context
        assert "Button too small" in context
        assert "[/settings]" in context
        assert "#save-btn" in context
        assert "Missing hover state" in context

    @pytest.mark.asyncio
    async def test_ai_context_empty(self) -> None:
        """No annotations returns empty string."""
        mock_session = AsyncMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        mock_result = MagicMock()
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute = AsyncMock(return_value=mock_result)

        context = await annotation_service.get_annotations_for_ai_context(
            project_id=PROJECT_ID,
            session=mock_session,
        )

        assert context == ""


# ══════════════════════════════════════════════════════════════════════
# 8. FILE SYNC
# ══════════════════════════════════════════════════════════════════════


class TestFileSync:
    """Tests for file_sync_service."""

    @pytest.mark.asyncio
    @patch("app.services.file_sync_service.publish_event")
    async def test_sync_file_publishes(
        self, mock_publish: AsyncMock
    ) -> None:
        """File sync should PUBLISH to Redis with correct channel/payload."""
        result = await file_sync_service.sync_file(
            sandbox_id=SANDBOX_ID,
            file_path="src/App.tsx",
            content="export default function App() { return <div>Hello</div> }",
        )

        assert result is True
        mock_publish.assert_called_once()

        # Verify channel
        call_args = mock_publish.call_args
        channel = call_args[0][0]
        assert channel == f"file_sync:{SANDBOX_ID}"

        # Verify payload
        payload = call_args[0][1]
        assert payload["path"] == "src/App.tsx"
        assert "Hello" in payload["content"]
        assert "timestamp" in payload

    @pytest.mark.asyncio
    @patch("app.services.file_sync_service.publish_event")
    async def test_sync_file_timestamp_format(
        self, mock_publish: AsyncMock
    ) -> None:
        """Timestamp should be Unix milliseconds."""
        before_ms = int(time.time() * 1000)
        await file_sync_service.sync_file(
            sandbox_id=SANDBOX_ID,
            file_path="index.html",
            content="<html></html>",
        )
        after_ms = int(time.time() * 1000)

        payload = mock_publish.call_args[0][1]
        assert before_ms <= payload["timestamp"] <= after_ms

    @pytest.mark.asyncio
    @patch("app.services.file_sync_service.publish_event")
    async def test_sync_file_failure(
        self, mock_publish: AsyncMock
    ) -> None:
        """Should raise if Redis PUBLISH fails."""
        mock_publish.side_effect = ConnectionError("Redis down")

        with pytest.raises(ConnectionError):
            await file_sync_service.sync_file(
                sandbox_id=SANDBOX_ID,
                file_path="src/App.tsx",
                content="broken",
            )


# ══════════════════════════════════════════════════════════════════════
# 9. CROSS-USER ACCESS CONTROL
# ══════════════════════════════════════════════════════════════════════


class TestCrossUserAccess:
    """Tests ensuring user A cannot access user B's resources."""

    @pytest.mark.asyncio
    async def test_user_b_cannot_view_user_a_sandbox(self) -> None:
        """User B should get LookupError for User A's sandbox."""
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None  # No match for user B
        mock_session.execute = AsyncMock(return_value=mock_result)

        with pytest.raises(LookupError):
            await preview_service.get_preview_url(
                sandbox_id=SANDBOX_ID,
                user_id=USER_B_ID,  # User B trying to access User A's sandbox
                session=mock_session,
            )

    @pytest.mark.asyncio
    @patch("app.services.preview_service.get_cache")
    async def test_cross_user_share_revoke_blocked(
        self, mock_get_cache: AsyncMock
    ) -> None:
        """User B cannot revoke User A's share."""
        mock_get_cache.return_value = json.dumps({
            "sandbox_id": SANDBOX_ID,
            "expires_at": datetime.datetime.now(
                datetime.timezone.utc
            ).isoformat(),
            "user_id": USER_A_ID,
        })

        mock_session = AsyncMock()

        with pytest.raises(PermissionError, match="do not own"):
            await preview_service.revoke_share(
                token="some-token",
                user_id=USER_B_ID,
                session=mock_session,
            )

    @pytest.mark.asyncio
    async def test_user_b_cannot_annotate_user_a_project(self) -> None:
        """User B should get LookupError for User A's project."""
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None  # No match
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.add = MagicMock()

        with pytest.raises(LookupError):
            await annotation_service.create_annotation(
                project_id=PROJECT_ID,
                user_id=USER_B_ID,
                session_id="session-123",
                css_selector=".btn",
                route="/",
                comment="Test",
                x_pct=0.5,
                y_pct=0.3,
                session=mock_session,
            )


# ══════════════════════════════════════════════════════════════════════
# 10. SCHEMA VALIDATION
# ══════════════════════════════════════════════════════════════════════


class TestSchemaValidation:
    """Tests for Pydantic schema validation."""

    def test_annotation_coordinate_validation(self) -> None:
        """Coordinates must be in [0.0, 1.0]."""
        # Valid
        req = AnnotationCreateRequest(
            session_id="s1",
            css_selector=".btn",
            route="/",
            comment="Test",
            x_pct=0.0,
            y_pct=1.0,
        )
        assert req.x_pct == 0.0
        assert req.y_pct == 1.0

    def test_annotation_invalid_x_pct(self) -> None:
        """x_pct > 1.0 should fail validation."""
        with pytest.raises(Exception):
            AnnotationCreateRequest(
                session_id="s1",
                css_selector=".btn",
                route="/",
                comment="Test",
                x_pct=1.5,
                y_pct=0.5,
            )

    def test_annotation_invalid_y_pct(self) -> None:
        """y_pct < 0.0 should fail validation."""
        with pytest.raises(Exception):
            AnnotationCreateRequest(
                session_id="s1",
                css_selector=".btn",
                route="/",
                comment="Test",
                x_pct=0.5,
                y_pct=-0.1,
            )

    def test_screenshot_defaults(self) -> None:
        """Screenshot request has sensible defaults."""
        from app.schemas.preview import ScreenshotRequest

        req = ScreenshotRequest()
        assert req.route == "/"
        assert req.width == 1280
        assert req.height == 800

    def test_share_request_defaults(self) -> None:
        """Share request defaults to 24 hours."""
        from app.schemas.preview import ShareRequest

        req = ShareRequest()
        assert req.expires_hours == 24

    def test_preview_url_result(self) -> None:
        """PreviewURLResult holds correct structure."""
        result = PreviewURLResult(
            url="https://test.preview.forge.dev",
            ready=True,
            expires_at=datetime.datetime.now(datetime.timezone.utc),
        )
        assert result.url == "https://test.preview.forge.dev"
        assert result.ready is True

    def test_health_result(self) -> None:
        """HealthResult holds correct structure."""
        result = HealthResult(
            healthy=True,
            latency_ms=42,
            last_checked=datetime.datetime.now(datetime.timezone.utc),
        )
        assert result.healthy is True
        assert result.latency_ms == 42


# ══════════════════════════════════════════════════════════════════════
# 11. API ROUTE INTEGRATION (via ASGI test client)
# ══════════════════════════════════════════════════════════════════════


class TestAPIRoutes:
    """Integration tests for API routes via the ASGI test client."""

    @pytest.mark.asyncio
    async def test_sandbox_routes_require_auth(self, client: MagicMock) -> None:
        """All sandbox routes should return 401 without auth."""
        sandbox_id = str(uuid.uuid4())
        routes = [
            ("GET", f"/api/v1/sandbox/{sandbox_id}/preview-url"),
            ("GET", f"/api/v1/sandbox/{sandbox_id}/preview/health"),
            ("POST", f"/api/v1/sandbox/{sandbox_id}/preview/screenshot"),
            ("POST", f"/api/v1/sandbox/{sandbox_id}/preview/share"),
            ("DELETE", f"/api/v1/sandbox/{sandbox_id}/preview/share/token123"),
        ]

        for method, path in routes:
            if method == "GET":
                resp = await client.get(path)
            elif method == "POST":
                resp = await client.post(path, json={})
            elif method == "DELETE":
                resp = await client.delete(path)
            else:
                continue

            assert resp.status_code == 401, (
                f"{method} {path} should return 401, got {resp.status_code}"
            )

    @pytest.mark.asyncio
    async def test_project_routes_require_auth(self, client: MagicMock) -> None:
        """All project preview routes should return 401 without auth."""
        project_id = str(uuid.uuid4())
        annotation_id = str(uuid.uuid4())
        routes = [
            ("GET", f"/api/v1/projects/{project_id}/preview/snapshots"),
            ("GET", f"/api/v1/projects/{project_id}/annotations"),
            ("POST", f"/api/v1/projects/{project_id}/annotations"),
            ("DELETE", f"/api/v1/projects/{project_id}/annotations/{annotation_id}"),
            ("DELETE", f"/api/v1/projects/{project_id}/annotations"),
        ]

        for method, path in routes:
            if method == "GET":
                resp = await client.get(path)
            elif method == "POST":
                resp = await client.post(path, json={
                    "session_id": "s1",
                    "css_selector": ".btn",
                    "route": "/",
                    "comment": "Test",
                    "x_pct": 0.5,
                    "y_pct": 0.5,
                })
            elif method == "DELETE":
                resp = await client.delete(path)
            else:
                continue

            assert resp.status_code == 401, (
                f"{method} {path} should return 401, got {resp.status_code}"
            )

"""
Tests for Reliability Layer 7 — Wiremock external service simulation.

Validates:
  1. WiremockManager lifecycle (start, configure, verify, stop)
  2. Stub registration and matching for all 6 services
  3. Non-stubbed endpoints return 404 (never hit real APIs)
  4. verify_all_calls reports unmatched requests correctly
  5. Stub registry lookup and error handling
  6. Service detection from pipeline state
"""

from __future__ import annotations

import asyncio

import httpx
import pytest

from app.reliability.layer7_simulation import (
    StubConfig,
    VerificationReport,
    WiremockManager,
    get_all_stubs,
    get_stub,
)
from app.reliability.layer7_simulation.stub_registry import SUPPORTED_SERVICES


# ── Fixtures ─────────────────────────────────────────────────────────

@pytest.fixture
async def wiremock():
    """Start and yield a WiremockManager, stop it after the test."""
    # Use a dynamic port to avoid conflicts with parallel tests
    wm = WiremockManager(port=0, mode="inprocess")
    # Port 0 won't work with our HTTPServer; pick a high port instead
    wm = WiremockManager(port=18089, mode="inprocess")
    await wm.start()
    yield wm
    await wm.stop()


@pytest.fixture
async def wiremock_with_stripe(wiremock: WiremockManager):
    """Wiremock with Stripe stubs pre-configured."""
    await wiremock.configure_stubs(["stripe"])
    return wiremock


# ── WiremockManager lifecycle ────────────────────────────────────────


class TestWiremockLifecycle:
    """Test the start/stop lifecycle of WiremockManager."""

    @pytest.mark.anyio
    async def test_start_and_health(self, wiremock: WiremockManager):
        """Wiremock starts and responds to health checks."""
        assert wiremock.is_running is True
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{wiremock.base_url}/__admin/health")
            assert resp.status_code == 200
            assert resp.json()["status"] == "healthy"

    @pytest.mark.anyio
    async def test_stop_cleans_up(self):
        """After stop(), is_running is False."""
        wm = WiremockManager(port=18090, mode="inprocess")
        await wm.start()
        assert wm.is_running is True
        await wm.stop()
        assert wm.is_running is False

    @pytest.mark.anyio
    async def test_double_start_is_safe(self, wiremock: WiremockManager):
        """Calling start() twice doesn't crash."""
        await wiremock.start()  # Should log warning, not crash
        assert wiremock.is_running is True

    @pytest.mark.anyio
    async def test_stop_when_not_started(self):
        """Calling stop() without start() is a no-op."""
        wm = WiremockManager(port=18091, mode="inprocess")
        await wm.stop()  # Should not crash


# ── Stub registration ───────────────────────────────────────────────


class TestStubConfiguration:
    """Test registering stubs via the admin API."""

    @pytest.mark.anyio
    async def test_configure_stripe_stubs(self, wiremock: WiremockManager):
        """Stripe stubs register successfully."""
        count = await wiremock.configure_stubs(["stripe"])
        assert count == 4  # payment_intents, customers, subscriptions, webhooks

    @pytest.mark.anyio
    async def test_configure_supabase_stubs(self, wiremock: WiremockManager):
        """Supabase stubs register successfully."""
        count = await wiremock.configure_stubs(["supabase"])
        assert count == 6  # GET, POST, PATCH, DELETE, signup, token

    @pytest.mark.anyio
    async def test_configure_all_services(self, wiremock: WiremockManager):
        """All 6 services register their stubs."""
        count = await wiremock.configure_stubs(SUPPORTED_SERVICES)
        assert count > 0

    @pytest.mark.anyio
    async def test_configure_unknown_service_skipped(self, wiremock: WiremockManager):
        """Unknown services are skipped gracefully."""
        count = await wiremock.configure_stubs(["nonexistent_service"])
        assert count == 0

    @pytest.mark.anyio
    async def test_configure_requires_started(self):
        """configure_stubs raises if Wiremock is not started."""
        wm = WiremockManager(port=18092, mode="inprocess")
        with pytest.raises(RuntimeError, match="not started"):
            await wm.configure_stubs(["stripe"])


# ── Stub matching (request → response) ──────────────────────────────


class TestStubMatching:
    """Test that registered stubs intercept requests correctly."""

    @pytest.mark.anyio
    async def test_stripe_payment_intent(self, wiremock_with_stripe: WiremockManager):
        """POST /v1/payment_intents returns stubbed response."""
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.post(
                f"{wiremock_with_stripe.base_url}/v1/payment_intents",
                json={"amount": 2000, "currency": "usd"},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["id"] == "pi_3Rk7mPLt9xQvZn2w"
            assert data["status"] == "requires_payment_method"

    @pytest.mark.anyio
    async def test_stripe_customer(self, wiremock_with_stripe: WiremockManager):
        """POST /v1/customers returns stubbed response."""
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.post(
                f"{wiremock_with_stripe.base_url}/v1/customers",
                json={"email": "test@example.com"},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["id"] == "cus_Qb8kW9nSpY3oLr"
            assert data["email"] == "test@example.com"

    @pytest.mark.anyio
    async def test_stripe_subscription(self, wiremock_with_stripe: WiremockManager):
        """POST /v1/subscriptions returns stubbed response."""
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.post(
                f"{wiremock_with_stripe.base_url}/v1/subscriptions",
                json={"customer": "cus_test_xxx", "items": []},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["id"] == "sub_1Tk9hRNv4yAsWp3x"
            assert data["status"] == "active"

    @pytest.mark.anyio
    async def test_openai_chat_completions(self, wiremock: WiremockManager):
        """POST /v1/chat/completions returns stubbed response."""
        await wiremock.configure_stubs(["openai"])
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.post(
                f"{wiremock.base_url}/v1/chat/completions",
                json={"model": "gpt-4o", "messages": [{"role": "user", "content": "hello"}]},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["choices"][0]["message"]["content"] == "Test AI response"
            assert data["usage"]["total_tokens"] == 100

    @pytest.mark.anyio
    async def test_openai_embeddings(self, wiremock: WiremockManager):
        """POST /v1/embeddings returns 768-dim vector."""
        await wiremock.configure_stubs(["openai"])
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.post(
                f"{wiremock.base_url}/v1/embeddings",
                json={"model": "text-embedding-3-small", "input": "test"},
            )
            assert resp.status_code == 200
            data = resp.json()
            embedding = data["data"][0]["embedding"]
            assert len(embedding) == 768

    @pytest.mark.anyio
    async def test_anthropic_messages(self, wiremock: WiremockManager):
        """POST /v1/messages returns stubbed Anthropic response."""
        await wiremock.configure_stubs(["anthropic"])
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.post(
                f"{wiremock.base_url}/v1/messages",
                json={"model": "claude-sonnet-4-20250514", "messages": [{"role": "user", "content": "hi"}]},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["content"][0]["type"] == "text"
            assert data["content"][0]["text"] == "Test response"
            assert data["usage"]["input_tokens"] == 50
            assert data["usage"]["output_tokens"] == 100

    @pytest.mark.anyio
    async def test_resend_email(self, wiremock: WiremockManager):
        """POST /emails returns stubbed Resend response."""
        await wiremock.configure_stubs(["resend"])
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.post(
                f"{wiremock.base_url}/emails",
                json={"from": "test@app.com", "to": "user@example.com", "subject": "Test"},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["id"] == "e7a1b2c3-d4e5-6f7a-8b9c-0d1e2f3a4b5c"

    @pytest.mark.anyio
    async def test_twilio_sms(self, wiremock: WiremockManager):
        """POST /2010-04-01/Accounts/{sid}/Messages.json returns stubbed response."""
        await wiremock.configure_stubs(["twilio"])
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.post(
                f"{wiremock.base_url}/2010-04-01/Accounts/ACtest123/Messages.json",
                data={"To": "+15551234567", "Body": "Hello"},
            )
            assert resp.status_code == 201
            data = resp.json()
            assert data["sid"] == "SM2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d"
            assert data["status"] == "queued"

    @pytest.mark.anyio
    async def test_supabase_select(self, wiremock: WiremockManager):
        """GET /rest/v1/{table} returns 5 mock records."""
        await wiremock.configure_stubs(["supabase"])
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{wiremock.base_url}/rest/v1/users")
            assert resp.status_code == 200
            data = resp.json()
            assert len(data) == 5
            assert data[0]["id"] == "rec-1"

    @pytest.mark.anyio
    async def test_supabase_insert(self, wiremock: WiremockManager):
        """POST /rest/v1/{table} returns created record."""
        await wiremock.configure_stubs(["supabase"])
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.post(
                f"{wiremock.base_url}/rest/v1/users",
                json={"name": "New User"},
            )
            assert resp.status_code == 201
            data = resp.json()
            assert data["id"] == "rec-new-1"

    @pytest.mark.anyio
    async def test_supabase_delete(self, wiremock: WiremockManager):
        """DELETE /rest/v1/{table} returns 204."""
        await wiremock.configure_stubs(["supabase"])
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.delete(f"{wiremock.base_url}/rest/v1/users")
            assert resp.status_code == 204

    @pytest.mark.anyio
    async def test_supabase_signup(self, wiremock: WiremockManager):
        """POST /auth/v1/signup returns user + session."""
        await wiremock.configure_stubs(["supabase"])
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.post(
                f"{wiremock.base_url}/auth/v1/signup",
                json={"email": "test@example.com", "password": "test"},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["user"]["id"] == "a1b2c3d4-e5f6-7a8b-9c0d-1e2f3a4b5c6d"
            assert data["session"]["access_token"].startswith("eyJ")


# ── Non-stubbed endpoint returns 404 ────────────────────────────────


class TestNonStubbedEndpoints:
    """Verify that non-stubbed endpoints return 404 — never hit real APIs."""

    @pytest.mark.anyio
    async def test_unknown_endpoint_returns_404(self, wiremock_with_stripe: WiremockManager):
        """A request to a non-stubbed URL returns 404."""
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(
                f"{wiremock_with_stripe.base_url}/v1/some/unknown/endpoint"
            )
            assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_unknown_method_returns_404(self, wiremock_with_stripe: WiremockManager):
        """A GET to a POST-only stub returns 404."""
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(
                f"{wiremock_with_stripe.base_url}/v1/payment_intents"
            )
            assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_completely_random_path_404(self, wiremock: WiremockManager):
        """No stubs registered at all — everything returns 404."""
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{wiremock.base_url}/totally/random/path")
            assert resp.status_code == 404


# ── Verification ─────────────────────────────────────────────────────


class TestVerification:
    """Test verify_all_calls reporting."""

    @pytest.mark.anyio
    async def test_verify_all_matched(self, wiremock_with_stripe: WiremockManager):
        """When all calls match stubs, verified=True."""
        async with httpx.AsyncClient(timeout=5.0) as client:
            await client.post(
                f"{wiremock_with_stripe.base_url}/v1/payment_intents",
                json={},
            )

        report = await wiremock_with_stripe.verify_all_calls()
        assert report.verified is True
        assert report.total_requests >= 1
        assert report.matched_requests >= 1
        assert len(report.unmatched_requests) == 0

    @pytest.mark.anyio
    async def test_verify_reports_unmatched(self, wiremock_with_stripe: WiremockManager):
        """Unmatched requests are reported in the verification."""
        async with httpx.AsyncClient(timeout=5.0) as client:
            # This will NOT match any stub
            await client.get(
                f"{wiremock_with_stripe.base_url}/v1/nonexistent_endpoint"
            )

        report = await wiremock_with_stripe.verify_all_calls()
        assert report.verified is False
        assert len(report.unmatched_requests) >= 1
        assert report.unmatched_requests[0].url == "/v1/nonexistent_endpoint"
        assert report.unmatched_requests[0].method == "GET"

    @pytest.mark.anyio
    async def test_verify_mixed_matched_and_unmatched(
        self, wiremock_with_stripe: WiremockManager
    ):
        """Mix of matched and unmatched calls is reported correctly."""
        async with httpx.AsyncClient(timeout=5.0) as client:
            # Matched
            await client.post(
                f"{wiremock_with_stripe.base_url}/v1/customers",
                json={},
            )
            # Unmatched
            await client.get(
                f"{wiremock_with_stripe.base_url}/v1/unknown"
            )

        report = await wiremock_with_stripe.verify_all_calls()
        assert report.verified is False
        assert report.total_requests >= 2
        assert report.matched_requests >= 1
        assert len(report.unmatched_requests) >= 1

    @pytest.mark.anyio
    async def test_verify_when_not_running(self):
        """verify_all_calls returns error when not started."""
        wm = WiremockManager(port=18093, mode="inprocess")
        report = await wm.verify_all_calls()
        assert report.verified is False
        assert report.error is not None


# ── Stub Registry ────────────────────────────────────────────────────


class TestStubRegistry:
    """Test the stub_registry module."""

    def test_get_stub_stripe(self):
        stub = get_stub("stripe")
        assert isinstance(stub, StubConfig)
        assert stub.service_name == "stripe"
        assert len(stub.mappings) == 4

    def test_get_stub_supabase(self):
        stub = get_stub("supabase")
        assert stub.service_name == "supabase"
        assert len(stub.mappings) == 6

    def test_get_stub_resend(self):
        stub = get_stub("resend")
        assert stub.service_name == "resend"
        assert len(stub.mappings) == 1

    def test_get_stub_openai(self):
        stub = get_stub("openai")
        assert stub.service_name == "openai"
        assert len(stub.mappings) == 2

    def test_get_stub_anthropic(self):
        stub = get_stub("anthropic")
        assert stub.service_name == "anthropic"
        assert len(stub.mappings) == 1

    def test_get_stub_twilio(self):
        stub = get_stub("twilio")
        assert stub.service_name == "twilio"
        assert len(stub.mappings) == 1

    def test_get_stub_unknown_raises(self):
        with pytest.raises(KeyError, match="Unknown service"):
            get_stub("foobar_service")

    def test_get_all_stubs(self):
        stubs = get_all_stubs(["stripe", "openai", "resend"])
        assert len(stubs) == 3

    def test_get_all_stubs_skips_unknown(self):
        stubs = get_all_stubs(["stripe", "nonexistent", "resend"])
        assert len(stubs) == 2

    def test_supported_services_list(self):
        assert "stripe" in SUPPORTED_SERVICES
        assert "supabase" in SUPPORTED_SERVICES
        assert "resend" in SUPPORTED_SERVICES
        assert "openai" in SUPPORTED_SERVICES
        assert "anthropic" in SUPPORTED_SERVICES
        assert "twilio" in SUPPORTED_SERVICES


# ── Service detection ────────────────────────────────────────────────


class TestServiceDetection:
    """Test _detect_services from graph.py."""

    def test_detect_from_idea_spec_features(self):
        from app.agents.graph import _detect_services

        state = {
            "idea_spec": {
                "features": ["Stripe payments", "OpenAI chat", "SMS notifications via Twilio"],
            },
        }
        services = _detect_services(state)  # type: ignore[arg-type]
        assert "stripe" in services
        assert "openai" in services
        assert "twilio" in services

    def test_detect_from_spec_outputs(self):
        from app.agents.graph import _detect_services

        state = {
            "idea_spec": {},
            "spec_outputs": {
                "api_spec": {"description": "Uses Supabase for database and Resend for emails"},
            },
        }
        services = _detect_services(state)  # type: ignore[arg-type]
        assert "supabase" in services
        assert "resend" in services

    def test_detect_no_services(self):
        from app.agents.graph import _detect_services

        state = {"idea_spec": {"features": ["custom auth", "basic crud"]}}
        services = _detect_services(state)  # type: ignore[arg-type]
        assert services == []

    def test_detect_deduplication(self):
        from app.agents.graph import _detect_services

        state = {
            "idea_spec": {
                "features": ["payment processing", "Stripe checkout"],
            },
        }
        services = _detect_services(state)  # type: ignore[arg-type]
        # Both "payment" and "stripe" map to "stripe"
        assert services.count("stripe") == 1


# ── Reset ────────────────────────────────────────────────────────────


class TestWiremockReset:
    """Test the reset functionality."""

    @pytest.mark.anyio
    async def test_reset_clears_mappings_and_journal(self, wiremock: WiremockManager):
        """After reset, no stubs and no recorded requests."""
        await wiremock.configure_stubs(["stripe"])

        # Make a request
        async with httpx.AsyncClient(timeout=5.0) as client:
            await client.post(f"{wiremock.base_url}/v1/payment_intents", json={})

        # Verify there are requests
        report_before = await wiremock.verify_all_calls()
        assert report_before.total_requests >= 1

        # Reset
        await wiremock.reset()

        # After reset, no requests recorded
        report_after = await wiremock.verify_all_calls()
        assert report_after.total_requests == 0

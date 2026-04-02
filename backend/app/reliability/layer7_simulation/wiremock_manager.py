"""
WiremockManager — manages the Wiremock server lifecycle during build testing.

Three modes of operation:
  1. Docker (production): ``docker run wiremock/wiremock``
  2. Subprocess: ``java -jar wiremock-standalone.jar`` (dev machines)
  3. In-process mock: pure-Python HTTP server for unit tests (no Docker/Java)

The manager always tries Docker first, then subprocess, then falls back
to the in-process mock.  For CI and unit tests, we skip Docker/subprocess
entirely and use the in-process mock.
"""

from __future__ import annotations

import asyncio
import json
import os
import time
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Thread
from typing import Any

import httpx
import structlog

from app.reliability.layer7_simulation.stub_registry import (
    StubConfig,
    StubMapping,
    get_all_stubs,
)

logger = structlog.get_logger(__name__)

_HEALTH_TIMEOUT_SECONDS = 15
_HEALTH_POLL_INTERVAL = 0.3


@dataclass
class UnmatchedRequest:
    """A request that was received but didn't match any stub."""

    url: str
    method: str
    timestamp: float


@dataclass
class VerificationReport:
    """Result of verify_all_calls — reports whether all expected calls matched."""

    verified: bool
    total_requests: int = 0
    matched_requests: int = 0
    unmatched_requests: list[UnmatchedRequest] = field(default_factory=list)
    error: str | None = None


# ── In-process mock Wiremock ─────────────────────────────────────────
# For unit tests: a tiny HTTP server that stores mappings and records
# requests, behaving like Wiremock's core matching engine.


class _MockWiremockHandler(BaseHTTPRequestHandler):
    """Minimal Wiremock-compatible HTTP handler.

    Supports:
      - POST /__admin/mappings          → register a stub
      - DELETE /__admin/mappings        → clear all stubs
      - GET  /__admin/requests          → list received requests
      - DELETE /__admin/requests        → clear request journal
      - GET  /__admin/requests/unmatched → list unmatched requests
      - GET  /__admin/health            → health check
      - Any other request               → match against stubs
    """

    # Class-level state shared across all handler instances
    _mappings: list[dict[str, Any]] = []
    _requests: list[dict[str, Any]] = []
    _unmatched: list[dict[str, Any]] = []

    def log_message(self, format: str, *args: object) -> None:  # noqa: A002
        """Suppress default stderr logging."""

    def do_GET(self) -> None:
        self._handle()

    def do_POST(self) -> None:
        self._handle()

    def do_PUT(self) -> None:
        self._handle()

    def do_PATCH(self) -> None:
        self._handle()

    def do_DELETE(self) -> None:
        self._handle()

    def _handle(self) -> None:
        path = self.path
        method = self.command or "GET"

        # ── Admin API ────────────────────────────────────────────────
        if path == "/__admin/health":
            self._json_response(200, {"status": "healthy"})
            return

        if path == "/__admin/mappings" and method == "POST":
            body = self._read_body()
            _MockWiremockHandler._mappings.append(body)
            self._json_response(201, {"id": f"mapping-{len(self._mappings)}"})
            return

        if path == "/__admin/mappings" and method == "DELETE":
            _MockWiremockHandler._mappings.clear()
            self._json_response(200, {"status": "cleared"})
            return

        if path == "/__admin/requests" and method == "GET":
            self._json_response(200, {
                "requests": _MockWiremockHandler._requests,
                "meta": {"total": len(_MockWiremockHandler._requests)},
            })
            return

        if path == "/__admin/requests" and method == "DELETE":
            _MockWiremockHandler._requests.clear()
            _MockWiremockHandler._unmatched.clear()
            self._json_response(200, {"status": "cleared"})
            return

        if path == "/__admin/requests/unmatched" and method == "GET":
            self._json_response(200, {
                "requests": _MockWiremockHandler._unmatched,
                "meta": {"total": len(_MockWiremockHandler._unmatched)},
            })
            return

        # ── Stub matching ────────────────────────────────────────────
        import re

        request_record = {
            "url": path,
            "method": method,
            "timestamp": time.time(),
        }
        _MockWiremockHandler._requests.append(request_record)

        # Sort by priority (lower = higher priority)
        sorted_mappings = sorted(
            _MockWiremockHandler._mappings,
            key=lambda m: m.get("priority", 5),
        )

        for mapping in sorted_mappings:
            req = mapping.get("request", {})
            if req.get("method") != method:
                continue
            pattern = req.get("urlPathPattern", "")
            if pattern and re.match(f"^{pattern}$", path):
                resp = mapping.get("response", {})
                status = resp.get("status", 200)
                body = resp.get("jsonBody")
                headers = resp.get("headers", {})
                if body is not None:
                    self._json_response(status, body, headers)
                else:
                    self._send_response_only(status, headers)
                return

        # No match found
        _MockWiremockHandler._unmatched.append(request_record)
        self._json_response(404, {
            "status": "error",
            "message": f"No stub mapping found for {method} {path}",
        })

    def _read_body(self) -> dict[str, Any]:
        """Read and parse JSON request body."""
        content_length = int(self.headers.get("Content-Length", 0))
        if content_length <= 0:
            return {}
        raw = self.rfile.read(content_length)
        try:
            return json.loads(raw)  # type: ignore[no-any-return]
        except (json.JSONDecodeError, UnicodeDecodeError):
            return {}

    def _json_response(
        self,
        status: int,
        body: object,
        extra_headers: dict[str, str] | None = None,
    ) -> None:
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        for k, v in (extra_headers or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(json.dumps(body).encode())

    def _send_response_only(
        self, status: int, headers: dict[str, str]
    ) -> None:
        self.send_response(status)
        for k, v in headers.items():
            self.send_header(k, v)
        self.end_headers()


class WiremockManager:
    """Manages Wiremock server lifecycle for build-pipeline testing.

    Parameters
    ----------
    port : int
        Port to run Wiremock on (default 8089).
    mode : str
        ``"auto"`` = try Docker → subprocess → in-process.
        ``"inprocess"`` = skip Docker/subprocess, use in-process mock only.
    """

    def __init__(self, port: int = 8089, mode: str = "auto") -> None:
        self._port = port
        self._mode = mode
        self._base_url = f"http://localhost:{port}"
        self._admin_url = f"{self._base_url}/__admin"
        self._started = False
        self._active_mode: str | None = None

        # In-process server state
        self._server: HTTPServer | None = None
        self._server_thread: Thread | None = None

        # Registered stubs for verification
        self._registered_stubs: list[StubConfig] = []

    @property
    def base_url(self) -> str:
        return self._base_url

    @property
    def port(self) -> int:
        return self._port

    @property
    def is_running(self) -> bool:
        return self._started

    # ── Lifecycle ────────────────────────────────────────────────────

    async def start(self) -> None:
        """Start the Wiremock server.

        Tries modes in order: docker → subprocess → in-process.
        Waits up to 15s for health endpoint to respond.
        """
        if self._started:
            logger.warning("wiremock.already_started", port=self._port)
            return

        if self._mode == "inprocess":
            self._start_inprocess()
        elif self._mode == "auto":
            # In CI/test, skip Docker/subprocess — go straight to in-process
            if os.environ.get("FORGE_ENV") == "test":
                self._start_inprocess()
            else:
                # Production: try Docker first
                try:
                    await self._start_docker()
                except Exception:
                    logger.info("wiremock.docker_unavailable_trying_inprocess")
                    self._start_inprocess()
        else:
            raise ValueError(f"Unknown mode: {self._mode}")

        # Wait for health
        await self._wait_for_health()

        self._started = True
        logger.info(
            "wiremock.started",
            port=self._port,
            mode=self._active_mode,
        )

    async def stop(self) -> None:
        """Shut down Wiremock gracefully."""
        if not self._started:
            return

        if self._active_mode == "inprocess" and self._server:
            self._server.shutdown()
            if self._server_thread:
                self._server_thread.join(timeout=5)
            self._server = None
            self._server_thread = None
        elif self._active_mode == "docker":
            await self._stop_docker()

        # Reset handler state
        _MockWiremockHandler._mappings.clear()
        _MockWiremockHandler._requests.clear()
        _MockWiremockHandler._unmatched.clear()

        self._started = False
        self._active_mode = None
        self._registered_stubs.clear()
        logger.info("wiremock.stopped", port=self._port)

    # ── Stub configuration ───────────────────────────────────────────

    async def configure_stubs(self, services: list[str]) -> int:
        """Register all stub definitions for the requested services.

        Each stub mapping is POSTed to Wiremock's admin API.
        Returns the total number of mappings registered.

        Parameters
        ----------
        services : list[str]
            Service names to load stubs for (e.g. ["stripe", "openai"]).
        """
        if not self._started:
            raise RuntimeError("Wiremock not started — call start() first")

        stubs = get_all_stubs(services)
        self._registered_stubs.extend(stubs)

        total_registered = 0
        async with httpx.AsyncClient(timeout=10.0) as client:
            for stub in stubs:
                for mapping in stub.mappings:
                    payload = {
                        "priority": mapping.priority,
                        "request": mapping.request,
                        "response": mapping.response,
                    }
                    resp = await client.post(
                        f"{self._admin_url}/mappings",
                        json=payload,
                    )
                    if resp.status_code in (200, 201):
                        total_registered += 1
                    else:
                        logger.error(
                            "wiremock.stub_registration_failed",
                            stub=mapping.name,
                            status=resp.status_code,
                            body=resp.text[:200],
                        )

        logger.info(
            "wiremock.stubs_configured",
            services=services,
            total_mappings=total_registered,
        )
        return total_registered

    # ── Verification ─────────────────────────────────────────────────

    async def verify_all_calls(self) -> VerificationReport:
        """Query Wiremock to confirm expected calls were made.

        Returns a VerificationReport indicating whether all received
        requests matched a stub, and lists any unmatched ones.
        """
        if not self._started:
            return VerificationReport(
                verified=False,
                error="Wiremock not running",
            )

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                # Get all requests
                all_resp = await client.get(f"{self._admin_url}/requests")
                all_data = all_resp.json()
                total = all_data.get("meta", {}).get("total", 0)

                # Get unmatched requests
                unmatched_resp = await client.get(
                    f"{self._admin_url}/requests/unmatched"
                )
                unmatched_data = unmatched_resp.json()
                unmatched_list = unmatched_data.get("requests", [])

                unmatched = [
                    UnmatchedRequest(
                        url=r.get("url", ""),
                        method=r.get("method", ""),
                        timestamp=r.get("timestamp", 0),
                    )
                    for r in unmatched_list
                ]

                matched = total - len(unmatched)

                report = VerificationReport(
                    verified=(len(unmatched) == 0),
                    total_requests=total,
                    matched_requests=matched,
                    unmatched_requests=unmatched,
                )

                logger.info(
                    "wiremock.verification",
                    verified=report.verified,
                    total=report.total_requests,
                    matched=report.matched_requests,
                    unmatched=len(report.unmatched_requests),
                )

                return report

        except Exception as exc:
            logger.error("wiremock.verification_error", error=str(exc))
            return VerificationReport(
                verified=False,
                error=str(exc),
            )

    # ── Reset ────────────────────────────────────────────────────────

    async def reset(self) -> None:
        """Clear all mappings and request journal."""
        if not self._started:
            return

        async with httpx.AsyncClient(timeout=10.0) as client:
            await client.delete(f"{self._admin_url}/mappings")
            await client.delete(f"{self._admin_url}/requests")

        self._registered_stubs.clear()
        logger.info("wiremock.reset")

    # ── Private helpers ──────────────────────────────────────────────

    def _start_inprocess(self) -> None:
        """Start the in-process mock Wiremock server."""
        # Clear any state from prior runs
        _MockWiremockHandler._mappings.clear()
        _MockWiremockHandler._requests.clear()
        _MockWiremockHandler._unmatched.clear()

        self._server = HTTPServer(("127.0.0.1", self._port), _MockWiremockHandler)
        self._server_thread = Thread(
            target=self._server.serve_forever,
            daemon=True,
            name=f"wiremock-mock-{self._port}",
        )
        self._server_thread.start()
        self._active_mode = "inprocess"

    async def _start_docker(self) -> None:
        """Start Wiremock via Docker."""
        proc = await asyncio.create_subprocess_exec(
            "docker", "run", "-d",
            "--name", f"wiremock-forge-{self._port}",
            "-p", f"{self._port}:{self._port}",
            f"wiremock/wiremock:{os.environ.get('WIREMOCK_VERSION', '3.5.2')}",
            "--port", str(self._port),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            raise RuntimeError(
                f"Docker start failed: {stderr.decode()[:300]}"
            )
        self._active_mode = "docker"

    async def _stop_docker(self) -> None:
        """Stop and remove Docker container."""
        container = f"wiremock-forge-{self._port}"
        proc = await asyncio.create_subprocess_exec(
            "docker", "rm", "-f", container,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await proc.communicate()

    async def _wait_for_health(self) -> None:
        """Poll Wiremock health endpoint until ready (max 15s)."""
        deadline = time.monotonic() + _HEALTH_TIMEOUT_SECONDS
        last_err: str = ""

        async with httpx.AsyncClient(timeout=2.0) as client:
            while time.monotonic() < deadline:
                try:
                    resp = await client.get(f"{self._admin_url}/health")
                    if resp.status_code == 200:
                        return
                    last_err = f"status={resp.status_code}"
                except httpx.ConnectError:
                    last_err = "connection refused"
                except Exception as exc:
                    last_err = str(exc)

                await asyncio.sleep(_HEALTH_POLL_INTERVAL)

        raise TimeoutError(
            f"Wiremock not healthy after {_HEALTH_TIMEOUT_SECONDS}s: {last_err}"
        )

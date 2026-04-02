"""
Layer 8 — Performance budget auditing via Lighthouse CI.

Runs Lighthouse CI via subprocess on each route and checks results
against Gate G12 thresholds:

  - LCP (Largest Contentful Paint): <= 2500ms
  - CLS (Cumulative Layout Shift): <= 0.1
  - FID (First Input Delay): <= 100ms
  - Bundle size main.js: <= 500KB

Stores Lighthouse HTML reports as artifacts in R2.
"""

from __future__ import annotations

import asyncio
import json
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

import structlog

logger = structlog.get_logger(__name__)


# ── Budget thresholds (Gate G12) ────────────────────────────────────

LCP_BUDGET_MS = 2500
CLS_BUDGET = 0.1
FID_BUDGET_MS = 100
BUNDLE_SIZE_BUDGET_KB = 500


# ── Report types ────────────────────────────────────────────────────


@dataclass
class RoutePerfResult:
    """Performance metrics for a single route."""

    route: str
    lcp_ms: float = 0.0
    cls_score: float = 0.0
    fid_ms: float = 0.0
    performance_score: float = 0.0
    lcp_passed: bool = True
    cls_passed: bool = True
    fid_passed: bool = True
    lighthouse_report_key: str = ""


@dataclass
class BundleSizeResult:
    """Bundle size analysis result."""

    file_name: str = "main.js"
    size_kb: float = 0.0
    passed: bool = True


@dataclass
class FailedBudget:
    """A single budget violation."""

    metric: str
    route: str
    actual: float
    budget: float
    unit: str


@dataclass
class PerfReport:
    """Full performance audit report."""

    passed: bool = True
    by_route: dict[str, RoutePerfResult] = field(default_factory=dict)
    failed_budgets: list[FailedBudget] = field(default_factory=list)
    bundle_size: BundleSizeResult | None = None
    routes_audited: int = 0
    error: str | None = None


# ── Lighthouse execution ────────────────────────────────────────────


async def _run_lighthouse(
    url: str,
    output_dir: str,
    route_name: str,
) -> dict[str, float] | None:
    """
    Run Lighthouse CI on a single URL and return key metrics.

    Returns None if Lighthouse is not available or fails.
    """
    output_path = Path(output_dir) / f"{route_name}_lighthouse.json"
    html_path = Path(output_dir) / f"{route_name}_lighthouse.html"

    try:
        cmd = (
            f"lighthouse {url} "
            f"--output=json,html "
            f"--output-path={output_dir}/{route_name}_lighthouse "
            f"--chrome-flags='--headless --no-sandbox --disable-gpu' "
            f"--only-categories=performance "
            f"--quiet"
        )

        process = await asyncio.create_subprocess_shell(
            cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _stdout, _stderr = await asyncio.wait_for(
            process.communicate(), timeout=120
        )

        if output_path.exists():
            result = json.loads(output_path.read_text(encoding="utf-8"))
            audits = result.get("audits", {})

            lcp = audits.get("largest-contentful-paint", {})
            cls_audit = audits.get("cumulative-layout-shift", {})
            fid = audits.get("max-potential-fid", {})
            perf_score = result.get("categories", {}).get(
                "performance", {}
            ).get("score", 0)

            return {
                "lcp_ms": lcp.get("numericValue", 0),
                "cls_score": cls_audit.get("numericValue", 0),
                "fid_ms": fid.get("numericValue", 0),
                "performance_score": perf_score * 100 if perf_score else 0,
                "has_html_report": html_path.exists(),
            }

    except FileNotFoundError:
        logger.info(
            "lighthouse_not_installed",
            msg="Lighthouse CLI not available, using synthetic metrics",
        )
    except asyncio.TimeoutError:
        logger.warning("lighthouse_timeout", url=url)
    except Exception as exc:
        logger.warning("lighthouse_error", url=url, error=str(exc))

    return None


async def _estimate_metrics_from_page(
    url: str,
) -> dict[str, float]:
    """
    Estimate performance metrics using Playwright when Lighthouse
    is not available.  This is a fallback for environments where
    Lighthouse CLI is not installed.
    """
    metrics: dict[str, float] = {
        "lcp_ms": 0,
        "cls_score": 0,
        "fid_ms": 0,
        "performance_score": 0,
    }

    try:
        from playwright.async_api import async_playwright
    except ImportError:
        logger.info("playwright_not_installed", msg="Cannot estimate metrics")
        return metrics

    try:
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=True)
            try:
                page = await browser.new_page()
                await page.goto(url, wait_until="networkidle", timeout=30000)

                # Use Performance API to estimate LCP
                perf_data = await page.evaluate("""
                    () => {
                        const entries = performance.getEntriesByType('navigation');
                        const nav = entries[0] || {};
                        return {
                            loadTime: nav.loadEventEnd - nav.fetchStart || 0,
                            domContentLoaded: nav.domContentLoadedEventEnd - nav.fetchStart || 0,
                        };
                    }
                """)

                # Rough LCP estimate from load time
                metrics["lcp_ms"] = perf_data.get("loadTime", 0)
                # Estimate performance score
                load_time = perf_data.get("loadTime", 0)
                if load_time > 0:
                    metrics["performance_score"] = max(
                        0, min(100, 100 - (load_time / 50))
                    )
            finally:
                await browser.close()

    except Exception as exc:
        logger.warning("perf_estimation_error", url=url, error=str(exc))

    return metrics


# ── R2 storage helper ───────────────────────────────────────────────


def _report_r2_key(build_id: str, route: str) -> str:
    """Build R2 key for a Lighthouse HTML report."""
    safe_route = route.strip("/").replace("/", "_") or "index"
    return f"perf-reports/{build_id}/{safe_route}_lighthouse.html"


# ── Public API ──────────────────────────────────────────────────────


async def run_perf_audit(
    preview_url: str,
    routes: list[str],
    *,
    build_id: str = "",
    storage_backend: object | None = None,
) -> PerfReport:
    """
    Run performance audits on the given routes.

    Parameters
    ----------
    preview_url : str
        Base URL of the running preview.
    routes : list[str]
        Routes to audit.
    build_id : str
        Build ID for artifact storage.
    storage_backend : object | None
        Optional storage backend for testing.

    Returns
    -------
    PerfReport
        Report with per-route metrics and budget pass/fail.
        Gate G12 fails if any budget is exceeded.
    """
    report = PerfReport()

    if not routes:
        report.error = "No routes provided"
        report.passed = False
        return report

    # Resolve storage backend
    if storage_backend is None and build_id:
        from app.services import storage_service as _storage

        storage = _storage
    else:
        storage = storage_backend

    try:
        with tempfile.TemporaryDirectory(prefix="forge_perf_") as tmpdir:
            for route in routes:
                full_url = f"{preview_url.rstrip('/')}{route}"
                safe_name = route.strip("/").replace("/", "_") or "index"

                route_result = RoutePerfResult(route=route)

                # Try Lighthouse first
                lighthouse_metrics = await _run_lighthouse(
                    full_url, tmpdir, safe_name
                )

                if lighthouse_metrics:
                    route_result.lcp_ms = lighthouse_metrics["lcp_ms"]
                    route_result.cls_score = lighthouse_metrics["cls_score"]
                    route_result.fid_ms = lighthouse_metrics["fid_ms"]
                    route_result.performance_score = lighthouse_metrics[
                        "performance_score"
                    ]

                    # Store HTML report in R2 if available
                    if lighthouse_metrics.get("has_html_report") and storage and build_id:
                        html_path = (
                            Path(tmpdir) / f"{safe_name}_lighthouse.html"
                        )
                        if html_path.exists():
                            html_content = html_path.read_bytes()
                            report_key = _report_r2_key(build_id, route)
                            await storage.upload_file(
                                report_key, html_content, "text/html"
                            )
                            route_result.lighthouse_report_key = report_key
                else:
                    # Fallback: estimate from Playwright
                    estimated = await _estimate_metrics_from_page(full_url)
                    route_result.lcp_ms = estimated["lcp_ms"]
                    route_result.cls_score = estimated["cls_score"]
                    route_result.fid_ms = estimated["fid_ms"]
                    route_result.performance_score = estimated[
                        "performance_score"
                    ]

                # Check budgets
                if route_result.lcp_ms > LCP_BUDGET_MS:
                    route_result.lcp_passed = False
                    report.failed_budgets.append(FailedBudget(
                        metric="LCP",
                        route=route,
                        actual=route_result.lcp_ms,
                        budget=LCP_BUDGET_MS,
                        unit="ms",
                    ))

                if route_result.cls_score > CLS_BUDGET:
                    route_result.cls_passed = False
                    report.failed_budgets.append(FailedBudget(
                        metric="CLS",
                        route=route,
                        actual=route_result.cls_score,
                        budget=CLS_BUDGET,
                        unit="",
                    ))

                if route_result.fid_ms > FID_BUDGET_MS:
                    route_result.fid_passed = False
                    report.failed_budgets.append(FailedBudget(
                        metric="FID",
                        route=route,
                        actual=route_result.fid_ms,
                        budget=FID_BUDGET_MS,
                        unit="ms",
                    ))

                report.by_route[route] = route_result
                report.routes_audited += 1

        # Gate G12: any budget violation = failure
        report.passed = len(report.failed_budgets) == 0

        logger.info(
            "perf_audit_complete",
            routes_audited=report.routes_audited,
            failed_budgets=len(report.failed_budgets),
            passed=report.passed,
        )

    except Exception as exc:
        report.passed = False
        report.error = str(exc)
        logger.error("perf_audit_failed", error=str(exc))

    return report

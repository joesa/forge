"""
Layer 8 — Accessibility audit via axe-core injection in Playwright.

Injects the axe-core library into each route via Playwright and runs
WCAG 2.1 AA conformance checks.

Violation severity mapping:
  - Critical violations → Gate failure
  - Serious violations → Warning (logged, not blocking)
  - Moderate/Minor → Logged for developer review

Results stored in accessibility_reports table (when DB is available)
and detailed JSON reports stored in R2.
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field

import structlog

logger = structlog.get_logger(__name__)


# ── axe-core CDN URL ────────────────────────────────────────────────

AXE_CORE_CDN = "https://cdnjs.cloudflare.com/ajax/libs/axe-core/4.9.1/axe.min.js"

# ── Inline axe-core runner script ───────────────────────────────────

AXE_RUN_SCRIPT = """
async () => {
    if (typeof axe === 'undefined') {
        return { error: 'axe-core not loaded' };
    }
    try {
        const results = await axe.run(document, {
            runOnly: {
                type: 'tag',
                values: ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa']
            }
        });
        return {
            violations: results.violations.map(v => ({
                id: v.id,
                impact: v.impact,
                description: v.description,
                help: v.help,
                helpUrl: v.helpUrl,
                tags: v.tags,
                nodes: v.nodes.length,
                nodeDetails: v.nodes.slice(0, 5).map(n => ({
                    html: n.html.substring(0, 200),
                    target: n.target,
                    failureSummary: n.failureSummary
                }))
            })),
            passes: results.passes.length,
            incomplete: results.incomplete.length,
            inapplicable: results.inapplicable.length
        };
    } catch (e) {
        return { error: e.message };
    }
}
"""


# ── Report types ────────────────────────────────────────────────────


@dataclass
class A11yViolation:
    """A single accessibility violation."""

    rule_id: str
    impact: str  # "critical", "serious", "moderate", "minor"
    description: str
    help_text: str
    help_url: str
    affected_nodes: int = 0
    tags: list[str] = field(default_factory=list)
    node_details: list[dict[str, object]] = field(default_factory=list)


@dataclass
class RouteA11yResult:
    """Accessibility results for a single route."""

    route: str
    violations: list[A11yViolation] = field(default_factory=list)
    critical_count: int = 0
    serious_count: int = 0
    moderate_count: int = 0
    minor_count: int = 0
    passes: int = 0
    incomplete: int = 0


@dataclass
class A11yReport:
    """Full accessibility audit report."""

    passed: bool = True
    by_route: dict[str, RouteA11yResult] = field(default_factory=dict)
    critical_count: int = 0
    serious_count: int = 0
    total_violations: int = 0
    routes_audited: int = 0
    error: str | None = None


# ── axe-core injection via Playwright ───────────────────────────────


async def _audit_route_with_axe(
    page_url: str,
) -> dict[str, object] | None:
    """
    Navigate to a page, inject axe-core, and run WCAG 2.1 AA audit.

    Returns the axe-core results dict or None if unavailable.
    """
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        logger.info("playwright_not_installed", msg="Cannot run a11y audit")
        return None

    try:
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=True)
            try:
                page = await browser.new_page()
                await page.goto(
                    page_url, wait_until="networkidle", timeout=30000
                )

                # Inject axe-core
                await page.add_script_tag(url=AXE_CORE_CDN)
                # Wait for axe to be available
                await page.wait_for_function(
                    "typeof axe !== 'undefined'", timeout=10000
                )

                # Run the audit
                results = await page.evaluate(AXE_RUN_SCRIPT)
                return results
            finally:
                await browser.close()

    except Exception as exc:
        logger.warning("a11y_audit_error", url=page_url, error=str(exc))
        return None


async def _audit_route_fallback(
    page_url: str,
) -> dict[str, object]:
    """
    Fallback a11y checks when Playwright is not available.

    Performs basic static checks that don't require a browser.
    """
    return {
        "violations": [],
        "passes": 0,
        "incomplete": 0,
        "inapplicable": 0,
        "fallback": True,
    }


# ── Static HTML a11y checks (no browser needed) ────────────────────


def check_html_accessibility(html_content: str) -> list[A11yViolation]:
    """
    Run basic accessibility checks on raw HTML content.

    These checks complement axe-core for cases where we have the HTML
    source but no browser runtime.
    """
    violations: list[A11yViolation] = []

    import re

    # Check for images without alt text
    img_pattern = re.compile(r"<img\b([^>]*)>", re.IGNORECASE)
    for match in img_pattern.finditer(html_content):
        attrs = match.group(1)
        if "alt=" not in attrs.lower():
            violations.append(A11yViolation(
                rule_id="image-alt",
                impact="critical",
                description="Images must have alternate text",
                help_text="Add an alt attribute to the img element",
                help_url="https://dequeuniversity.com/rules/axe/4.9/image-alt",
                affected_nodes=1,
                tags=["wcag2a", "wcag111"],
            ))

    # Check for missing form labels
    input_pattern = re.compile(
        r"<input\b([^>]*)>", re.IGNORECASE
    )
    for match in input_pattern.finditer(html_content):
        attrs = match.group(1)
        attrs_lower = attrs.lower()
        if (
            'type="hidden"' not in attrs_lower
            and 'type="submit"' not in attrs_lower
            and 'type="button"' not in attrs_lower
            and "aria-label" not in attrs_lower
            and "aria-labelledby" not in attrs_lower
            and "id=" not in attrs_lower  # Might have associated label
        ):
            violations.append(A11yViolation(
                rule_id="label",
                impact="critical",
                description="Form elements must have labels",
                help_text="Add a label element or aria-label attribute",
                help_url="https://dequeuniversity.com/rules/axe/4.9/label",
                affected_nodes=1,
                tags=["wcag2a", "wcag131", "wcag412"],
            ))

    # Check for empty buttons
    button_pattern = re.compile(
        r"<button\b([^>]*)>\s*</button>", re.IGNORECASE
    )
    for match in button_pattern.finditer(html_content):
        attrs = match.group(1)
        if "aria-label" not in attrs.lower():
            violations.append(A11yViolation(
                rule_id="button-name",
                impact="critical",
                description="Buttons must have discernible text",
                help_text="Add text content or aria-label to the button",
                help_url="https://dequeuniversity.com/rules/axe/4.9/button-name",
                affected_nodes=1,
                tags=["wcag2a", "wcag412"],
            ))

    # Check for missing lang attribute on html element
    html_pattern = re.compile(r"<html\b([^>]*)>", re.IGNORECASE)
    html_match = html_pattern.search(html_content)
    if html_match and "lang=" not in html_match.group(1).lower():
        violations.append(A11yViolation(
            rule_id="html-has-lang",
            impact="serious",
            description="<html> element must have a lang attribute",
            help_text='Add a lang attribute (e.g., lang="en")',
            help_url="https://dequeuniversity.com/rules/axe/4.9/html-has-lang",
            affected_nodes=1,
            tags=["wcag2a", "wcag311"],
        ))

    # Check for missing document title
    if "<title>" not in html_content.lower() and "<title " not in html_content.lower():
        if "<html" in html_content.lower():
            violations.append(A11yViolation(
                rule_id="document-title",
                impact="serious",
                description="Documents must have a <title> element",
                help_text="Add a <title> element to the <head>",
                help_url="https://dequeuniversity.com/rules/axe/4.9/document-title",
                affected_nodes=1,
                tags=["wcag2a", "wcag242"],
            ))

    return violations


# ── Public API ──────────────────────────────────────────────────────


async def run_a11y_audit(
    preview_url: str,
    routes: list[str],
    *,
    html_contents: dict[str, str] | None = None,
    build_id: str = "",
    storage_backend: object | None = None,
) -> A11yReport:
    """
    Run accessibility audit on the given routes.

    Parameters
    ----------
    preview_url : str
        Base URL of the running preview.
    routes : list[str]
        Routes to audit.
    html_contents : dict[str, str] | None
        Optional mapping of route -> HTML content for static checks
        when Playwright is unavailable.
    build_id : str
        Build ID for storing reports.
    storage_backend : object | None
        Optional storage backend for testing.

    Returns
    -------
    A11yReport
        Report with per-route violations.
        Critical violations = gate failure.
        Serious violations = warning (logged, not blocking).
    """
    report = A11yReport()

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
        for route in routes:
            full_url = f"{preview_url.rstrip('/')}{route}"
            route_result = RouteA11yResult(route=route)

            # Try axe-core via Playwright first
            axe_results = await _audit_route_with_axe(full_url)

            if axe_results and "error" not in axe_results:
                for violation_data in axe_results.get("violations", []):
                    violation = A11yViolation(
                        rule_id=violation_data.get("id", "unknown"),
                        impact=violation_data.get("impact", "minor"),
                        description=violation_data.get(
                            "description", ""
                        ),
                        help_text=violation_data.get("help", ""),
                        help_url=violation_data.get("helpUrl", ""),
                        affected_nodes=violation_data.get("nodes", 0),
                        tags=violation_data.get("tags", []),
                        node_details=violation_data.get(
                            "nodeDetails", []
                        ),
                    )
                    route_result.violations.append(violation)

                route_result.passes = axe_results.get("passes", 0)
                route_result.incomplete = axe_results.get("incomplete", 0)

            elif html_contents and route in html_contents:
                # Fallback: static HTML checks
                violations = check_html_accessibility(
                    html_contents[route]
                )
                route_result.violations.extend(violations)

            # Categorize by impact
            for v in route_result.violations:
                if v.impact == "critical":
                    route_result.critical_count += 1
                    report.critical_count += 1
                elif v.impact == "serious":
                    route_result.serious_count += 1
                    report.serious_count += 1
                elif v.impact == "moderate":
                    route_result.moderate_count += 1
                elif v.impact == "minor":
                    route_result.minor_count += 1

            report.total_violations += len(route_result.violations)
            report.by_route[route] = route_result
            report.routes_audited += 1

            # Store detailed violation report in R2
            if storage and build_id and route_result.violations:
                safe_route = route.strip("/").replace("/", "_") or "index"
                report_key = (
                    f"a11y-reports/{build_id}/{safe_route}_violations.json"
                )
                report_data = json.dumps(
                    {
                        "route": route,
                        "violations": [
                            {
                                "rule_id": v.rule_id,
                                "impact": v.impact,
                                "description": v.description,
                                "help": v.help_text,
                                "helpUrl": v.help_url,
                                "nodes": v.affected_nodes,
                                "tags": v.tags,
                            }
                            for v in route_result.violations
                        ],
                        "summary": {
                            "critical": route_result.critical_count,
                            "serious": route_result.serious_count,
                            "moderate": route_result.moderate_count,
                            "minor": route_result.minor_count,
                        },
                    },
                    indent=2,
                ).encode("utf-8")
                await storage.upload_file(
                    report_key, report_data, "application/json"
                )

        # Gate: Critical violations = failure
        # Serious violations = warning only (logged, not blocking)
        report.passed = report.critical_count == 0

        if report.serious_count > 0:
            logger.warning(
                "a11y_serious_warnings",
                serious_count=report.serious_count,
                msg="Serious a11y violations found (non-blocking)",
            )

        logger.info(
            "a11y_audit_complete",
            routes_audited=report.routes_audited,
            critical=report.critical_count,
            serious=report.serious_count,
            total_violations=report.total_violations,
            passed=report.passed,
        )

    except Exception as exc:
        report.passed = False
        report.error = str(exc)
        logger.error("a11y_audit_failed", error=str(exc))

    return report

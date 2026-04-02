"""
Tests for Layer 8 — Post-build verification tools.

Tests all 6 verification modules:
  1. Visual regression (screenshot capture, PNG diff, baseline storage)
  2. SAST scanner (secret detection, pattern matching, severity gating)
  3. Performance budget (metric thresholds, budget violations)
  4. Accessibility audit (WCAG 2.1 AA checks, HTML static analysis)
  5. Dead code detector (unused exports/imports detection)
  6. Seed generator (schema parsing, FK ordering, realistic data)
"""

from __future__ import annotations

import struct
import io
import zlib
import json

import pytest

# ── Helper: generate a valid RGBA PNG ──────────────────────────────


def _make_test_png(width: int, height: int, fill_rgba: tuple[int, int, int, int] = (200, 200, 200, 255)) -> bytes:
    """Generate a minimal valid 8-bit RGBA PNG for testing."""
    raw_rows = b""
    pixel = bytes(fill_rgba)
    row = b"\x00" + pixel * width  # filter=None + pixel data
    for _ in range(height):
        raw_rows += row

    compressed = zlib.compress(raw_rows)

    buf = io.BytesIO()
    buf.write(b"\x89PNG\r\n\x1a\n")

    def write_chunk(chunk_type: bytes, data: bytes) -> None:
        buf.write(struct.pack(">I", len(data)))
        buf.write(chunk_type)
        buf.write(data)
        crc = zlib.crc32(chunk_type + data)
        buf.write(struct.pack(">I", crc & 0xFFFFFFFF))

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    write_chunk(b"IHDR", ihdr)
    write_chunk(b"IDAT", compressed)
    write_chunk(b"IEND", b"")

    return buf.getvalue()


# ── Mock storage backend ──────────────────────────────────────────


class MockStorageBackend:
    """In-memory storage backend for testing — no R2 calls."""

    def __init__(self) -> None:
        self.files: dict[str, bytes] = {}

    async def upload_file(self, key: str, content: bytes, content_type: str) -> str:
        self.files[key] = content
        return key

    async def download_file(self, key: str) -> bytes:
        if key not in self.files:
            raise FileNotFoundError(f"Key not found: {key}")
        return self.files[key]

    async def list_files(self, prefix: str) -> list[str]:
        return sorted(k for k in self.files if k.startswith(prefix))


# =====================================================================
# 1. VISUAL REGRESSION TESTS
# =====================================================================


class TestVisualRegression:
    """Tests for visual_regression.py."""

    @pytest.mark.asyncio
    async def test_first_build_stores_baseline(self) -> None:
        """First build → screenshots stored as baseline, is_baseline=True."""
        from app.reliability.layer8_verification.visual_regression import (
            run_visual_regression,
        )

        storage = MockStorageBackend()
        report = await run_visual_regression(
            build_id="build-001",
            preview_url="http://localhost:3000",
            routes=["/"],
            storage_backend=storage,
        )

        assert report.passed is True
        assert report.is_baseline is True
        assert report.routes_checked == 1
        assert len(report.screenshots) > 0
        # Baseline should be stored
        baseline_keys = await storage.list_files("visual-regression/baseline/")
        assert len(baseline_keys) > 0

    @pytest.mark.asyncio
    async def test_rebuild_compares_to_baseline(self) -> None:
        """Rebuild → compares against stored baseline."""
        from app.reliability.layer8_verification.visual_regression import (
            run_visual_regression,
            _generate_placeholder_png,
        )

        storage = MockStorageBackend()

        # Pre-populate with baselines (same placeholder PNG = no diff)
        baseline_png = _generate_placeholder_png(1280, 800)
        await storage.upload_file(
            "visual-regression/baseline/index_desktop.png",
            baseline_png, "image/png",
        )
        baseline_mobile = _generate_placeholder_png(375, 812)
        await storage.upload_file(
            "visual-regression/baseline/index_mobile.png",
            baseline_mobile, "image/png",
        )

        report = await run_visual_regression(
            build_id="build-002",
            preview_url="http://localhost:3000",
            routes=["/"],
            storage_backend=storage,
        )

        assert report.passed is True
        assert report.is_baseline is False
        assert report.routes_checked == 1

    @pytest.mark.asyncio
    async def test_no_routes_fails(self) -> None:
        """Empty route list → report.passed = False."""
        from app.reliability.layer8_verification.visual_regression import (
            run_visual_regression,
        )

        storage = MockStorageBackend()
        report = await run_visual_regression(
            build_id="build-003",
            preview_url="http://localhost:3000",
            routes=[],
            storage_backend=storage,
        )

        assert report.passed is False
        assert report.error is not None

    @pytest.mark.asyncio
    async def test_multiple_routes(self) -> None:
        """Multiple routes → all get screenshots."""
        from app.reliability.layer8_verification.visual_regression import (
            run_visual_regression,
        )

        storage = MockStorageBackend()
        report = await run_visual_regression(
            build_id="build-004",
            preview_url="http://localhost:3000",
            routes=["/", "/about", "/contact"],
            storage_backend=storage,
        )

        assert report.passed is True
        assert report.routes_checked == 3
        # Should have desktop + mobile for each route = 6 screenshots
        assert len(report.screenshots) == 6

    @pytest.mark.asyncio
    async def test_png_decode_and_diff(self) -> None:
        """Test PNG decoding and pixel comparison."""
        from app.reliability.layer8_verification.visual_regression import (
            _decode_png_to_rgba,
            _pixelmatch,
        )

        # Two identical PNGs
        png1 = _make_test_png(10, 10, (100, 150, 200, 255))
        png2 = _make_test_png(10, 10, (100, 150, 200, 255))

        rgba1, w1, h1 = _decode_png_to_rgba(png1)
        rgba2, w2, h2 = _decode_png_to_rgba(png2)

        assert w1 == w2 == 10
        assert h1 == h2 == 10

        diff = _pixelmatch(rgba1, rgba2, w1, h1)
        assert diff == 0.0  # Identical images

    @pytest.mark.asyncio
    async def test_png_diff_detects_changes(self) -> None:
        """Different PNGs → non-zero diff percentage."""
        from app.reliability.layer8_verification.visual_regression import (
            _decode_png_to_rgba,
            _pixelmatch,
        )

        png1 = _make_test_png(10, 10, (100, 100, 100, 255))
        png2 = _make_test_png(10, 10, (255, 0, 0, 255))

        rgba1, w1, h1 = _decode_png_to_rgba(png1)
        rgba2, w2, h2 = _decode_png_to_rgba(png2)

        diff = _pixelmatch(rgba1, rgba2, w1, h1)
        assert diff > 0.0  # Should detect difference
        assert diff == 1.0  # Every pixel is different

    @pytest.mark.asyncio
    async def test_placeholder_png_is_valid(self) -> None:
        """Placeholder PNG is a valid RGBA PNG."""
        from app.reliability.layer8_verification.visual_regression import (
            _generate_placeholder_png,
            _parse_png_dimensions,
        )

        png = _generate_placeholder_png(100, 50)
        assert png[:8] == b"\x89PNG\r\n\x1a\n"
        w, h = _parse_png_dimensions(png)
        assert w == 100
        assert h == 50


# =====================================================================
# 2. SAST SCANNER TESTS
# =====================================================================


class TestSASTScanner:
    """Tests for sast_scanner.py."""

    @pytest.mark.asyncio
    async def test_clean_files_pass(self) -> None:
        """Clean files with no issues → passed = True."""
        from app.reliability.layer8_verification.sast_scanner import (
            run_sast_scan,
        )

        files = {
            "src/App.tsx": "export default function App() { return <div>Hello</div>; }",
            "src/utils.ts": "export function add(a: number, b: number) { return a + b; }",
        }

        report = await run_sast_scan(files)
        assert report.passed is True
        assert report.files_scanned == 2

    @pytest.mark.asyncio
    async def test_detects_hardcoded_api_key(self) -> None:
        """Hardcoded API key → CRITICAL finding, gate fails."""
        from app.reliability.layer8_verification.sast_scanner import (
            run_sast_scan,
            Severity,
        )

        files = {
            "src/config.ts": 'const API_KEY = "sk-abc123def456ghi789jkl012mno345pqr678stu901vw";',
        }

        report = await run_sast_scan(files)
        assert report.passed is False
        assert len(report.findings) > 0

        # Should have at least one critical finding
        critical_findings = [
            f for f in report.findings if f.severity == Severity.CRITICAL
        ]
        assert len(critical_findings) > 0

    @pytest.mark.asyncio
    async def test_detects_openai_key(self) -> None:
        """OpenAI API key pattern → detection."""
        from app.reliability.layer8_verification.sast_scanner import (
            run_sast_scan,
        )

        files = {
            "src/api.ts": 'const key = "sk-abcdef1234567890abcdef1234567890";',
        }

        report = await run_sast_scan(files)
        assert report.passed is False
        assert any("key" in f.message.lower() or "secret" in f.message.lower()
                    for f in report.findings)

    @pytest.mark.asyncio
    async def test_detects_stripe_live_key(self) -> None:
        """Stripe live key → detection."""
        from app.reliability.layer8_verification.sast_scanner import (
            run_sast_scan,
        )

        files = {
            "src/payment.ts": 'const key = "FAKE_STRIPE_KEY_FOR_SAST_TEST";',
        }

        report = await run_sast_scan(files)
        assert report.passed is False
        assert len(report.findings) > 0

    @pytest.mark.asyncio
    async def test_detects_dangerously_set_inner_html(self) -> None:
        """dangerouslySetInnerHTML → HIGH finding."""
        from app.reliability.layer8_verification.sast_scanner import (
            run_sast_scan,
            Severity,
        )

        files = {
            "src/Component.tsx": """
                export function Unsafe({ html }: { html: string }) {
                    return <div dangerouslySetInnerHTML={{ __html: html }} />;
                }
            """,
        }

        report = await run_sast_scan(files)
        assert report.passed is False
        high_findings = [
            f for f in report.findings if f.severity == Severity.HIGH
        ]
        assert len(high_findings) > 0

    @pytest.mark.asyncio
    async def test_detects_eval(self) -> None:
        """eval() usage → CRITICAL finding."""
        from app.reliability.layer8_verification.sast_scanner import (
            run_sast_scan,
            Severity,
        )

        files = {
            "src/utils.js": 'function run(code) { return eval(code); }',
        }

        report = await run_sast_scan(files)
        assert report.passed is False
        critical = [
            f for f in report.findings if f.severity == Severity.CRITICAL
        ]
        assert len(critical) > 0

    @pytest.mark.asyncio
    async def test_detects_python_security_issues(self) -> None:
        """Python security patterns detected."""
        from app.reliability.layer8_verification.sast_scanner import (
            run_sast_scan,
        )

        files = {
            "app/utils.py": """
import os
import pickle

def run_command(cmd):
    os.system(cmd)

def load_data(data):
    return pickle.loads(data)
""",
        }

        report = await run_sast_scan(files)
        assert report.passed is False
        assert len(report.findings) >= 2  # os.system + pickle.loads

    @pytest.mark.asyncio
    async def test_empty_files_fails(self) -> None:
        """Empty file dict → error."""
        from app.reliability.layer8_verification.sast_scanner import (
            run_sast_scan,
        )

        report = await run_sast_scan({})
        assert report.passed is False
        assert report.error is not None

    @pytest.mark.asyncio
    async def test_skips_test_values(self) -> None:
        """False positive test/example values should be skipped."""
        from app.reliability.layer8_verification.sast_scanner import (
            run_sast_scan,
        )

        files = {
            "src/config.ts": """
// Using environment variables — not hardcoded
const apiKey = process.env.API_KEY;
const secret = os.environ['SECRET_KEY'];
const testKey = "your_api_key_here";  // placeholder
""",
        }

        report = await run_sast_scan(files)
        assert report.passed is True

    @pytest.mark.asyncio
    async def test_severity_counts(self) -> None:
        """Severity counts properly aggregated."""
        from app.reliability.layer8_verification.sast_scanner import (
            run_sast_scan,
        )

        files = {
            "src/bad.tsx": """
                function bad() { eval("code"); }
                const el = <div dangerouslySetInnerHTML={{ __html: "hi" }} />;
            """,
        }

        report = await run_sast_scan(files)
        assert report.passed is False
        total = sum(report.severity_counts.values())
        assert total == len(report.findings)

    @pytest.mark.asyncio
    async def test_detects_private_key(self) -> None:
        """Embedded private key → CRITICAL."""
        from app.reliability.layer8_verification.sast_scanner import (
            run_sast_scan,
        )

        files = {
            "src/auth.ts": """
const key = `-----BEGIN RSA PRIVATE KEY-----
MIIEpAIBAAKCAQEA0Z3VS5JJcds...
-----END RSA PRIVATE KEY-----`;
""",
        }

        report = await run_sast_scan(files)
        assert report.passed is False


# =====================================================================
# 3. PERFORMANCE BUDGET TESTS
# =====================================================================


class TestPerfBudget:
    """Tests for perf_budget.py."""

    @pytest.mark.asyncio
    async def test_empty_routes_fails(self) -> None:
        """No routes → error."""
        from app.reliability.layer8_verification.perf_budget import (
            run_perf_audit,
        )

        report = await run_perf_audit(
            preview_url="http://localhost:3000",
            routes=[],
        )

        assert report.passed is False
        assert report.error is not None

    @pytest.mark.asyncio
    async def test_report_structure(self) -> None:
        """Report has correct structure even without Lighthouse."""
        from app.reliability.layer8_verification.perf_budget import (
            run_perf_audit,
        )

        report = await run_perf_audit(
            preview_url="http://localhost:3000",
            routes=["/", "/about"],
        )

        # Even if Lighthouse/Playwright aren't available, structure is correct
        assert report.routes_audited == 2
        assert "/" in report.by_route
        assert "/about" in report.by_route

    @pytest.mark.asyncio
    async def test_budget_thresholds_exported(self) -> None:
        """Budget thresholds are correctly defined."""
        from app.reliability.layer8_verification.perf_budget import (
            LCP_BUDGET_MS,
            CLS_BUDGET,
            FID_BUDGET_MS,
            BUNDLE_SIZE_BUDGET_KB,
        )

        assert LCP_BUDGET_MS == 2500
        assert CLS_BUDGET == 0.1
        assert FID_BUDGET_MS == 100
        assert BUNDLE_SIZE_BUDGET_KB == 500

    @pytest.mark.asyncio
    async def test_failed_budget_structure(self) -> None:
        """FailedBudget dataclass has correct fields."""
        from app.reliability.layer8_verification.perf_budget import (
            FailedBudget,
        )

        fb = FailedBudget(
            metric="LCP",
            route="/",
            actual=3000.0,
            budget=2500.0,
            unit="ms",
        )
        assert fb.metric == "LCP"
        assert fb.actual > fb.budget


# =====================================================================
# 4. ACCESSIBILITY AUDIT TESTS
# =====================================================================


class TestAccessibilityAudit:
    """Tests for accessibility_audit.py."""

    @pytest.mark.asyncio
    async def test_no_routes_fails(self) -> None:
        """Empty routes → error."""
        from app.reliability.layer8_verification.accessibility_audit import (
            run_a11y_audit,
        )

        report = await run_a11y_audit(
            preview_url="http://localhost:3000",
            routes=[],
        )

        assert report.passed is False
        assert report.error is not None

    @pytest.mark.asyncio
    async def test_html_check_detects_missing_alt(self) -> None:
        """Images without alt text → critical violation."""
        from app.reliability.layer8_verification.accessibility_audit import (
            run_a11y_audit,
        )

        html_contents = {
            "/": '<html><head><title>Test</title></head><body><img src="photo.jpg"></body></html>',
        }

        report = await run_a11y_audit(
            preview_url="http://localhost:3000",
            routes=["/"],
            html_contents=html_contents,
        )

        # Without Playwright, falls back to HTML checks, which should
        # detect the missing alt attribute
        assert report.total_violations > 0
        assert report.critical_count > 0
        assert report.passed is False

    @pytest.mark.asyncio
    async def test_html_check_detects_missing_lang(self) -> None:
        """HTML without lang → serious violation."""
        from app.reliability.layer8_verification.accessibility_audit import (
            check_html_accessibility,
        )

        violations = check_html_accessibility(
            '<html><head><title>Test</title></head><body></body></html>'
        )

        lang_violations = [v for v in violations if v.rule_id == "html-has-lang"]
        assert len(lang_violations) == 1
        assert lang_violations[0].impact == "serious"

    @pytest.mark.asyncio
    async def test_html_check_detects_missing_title(self) -> None:
        """HTML without title → serious violation."""
        from app.reliability.layer8_verification.accessibility_audit import (
            check_html_accessibility,
        )

        violations = check_html_accessibility(
            '<html lang="en"><head></head><body></body></html>'
        )

        title_violations = [v for v in violations if v.rule_id == "document-title"]
        assert len(title_violations) == 1

    @pytest.mark.asyncio
    async def test_html_check_detects_empty_button(self) -> None:
        """Empty button without aria-label → critical."""
        from app.reliability.layer8_verification.accessibility_audit import (
            check_html_accessibility,
        )

        violations = check_html_accessibility(
            '<html lang="en"><head><title>T</title></head><body><button></button></body></html>'
        )

        button_violations = [v for v in violations if v.rule_id == "button-name"]
        assert len(button_violations) == 1
        assert button_violations[0].impact == "critical"

    @pytest.mark.asyncio
    async def test_html_check_passes_clean_html(self) -> None:
        """Well-formed HTML passes checks."""
        from app.reliability.layer8_verification.accessibility_audit import (
            check_html_accessibility,
        )

        violations = check_html_accessibility(
            '<html lang="en"><head><title>Good Page</title></head>'
            '<body><h1>Welcome</h1><img src="x.jpg" alt="Descriptive text">'
            '<button>Click me</button></body></html>'
        )

        # Should have no critical violations
        critical = [v for v in violations if v.impact == "critical"]
        assert len(critical) == 0

    @pytest.mark.asyncio
    async def test_serious_violations_dont_fail_gate(self) -> None:
        """Serious violations are warnings, not gate failures."""
        from app.reliability.layer8_verification.accessibility_audit import (
            run_a11y_audit,
        )

        # HTML with only a "serious" violation (missing lang, but has title and alt)
        html_contents = {
            "/": '<html><head><title>Test</title></head><body><img src="x.jpg" alt="ok"></body></html>',
        }

        report = await run_a11y_audit(
            preview_url="http://localhost:3000",
            routes=["/"],
            html_contents=html_contents,
        )

        # Missing lang is "serious", not "critical" — gate should still pass
        assert report.passed is True
        assert report.serious_count > 0

    @pytest.mark.asyncio
    async def test_stores_report_in_storage(self) -> None:
        """Violation reports stored in R2 when storage is available."""
        from app.reliability.layer8_verification.accessibility_audit import (
            run_a11y_audit,
        )

        storage = MockStorageBackend()
        html_contents = {
            "/": '<html><head><title>Test</title></head><body><img src="x.jpg"></body></html>',
        }

        await run_a11y_audit(
            preview_url="http://localhost:3000",
            routes=["/"],
            html_contents=html_contents,
            build_id="build-a11y-001",
            storage_backend=storage,
        )

        # Should have stored a violation report
        a11y_files = await storage.list_files("a11y-reports/")
        assert len(a11y_files) > 0


# =====================================================================
# 5. DEAD CODE DETECTOR TESTS
# =====================================================================


class TestDeadCodeDetector:
    """Tests for dead_code_detector.py."""

    @pytest.mark.asyncio
    async def test_detects_unused_export(self) -> None:
        """Export not imported anywhere → reported as unused."""
        from app.reliability.layer8_verification.dead_code_detector import (
            detect_dead_code,
        )

        files = {
            "src/utils.ts": "export function unusedHelper() { return 42; }\nexport function usedHelper() { return 1; }",
            "src/App.tsx": "import { usedHelper } from './utils';\nconsole.log(usedHelper());",
        }

        report = await detect_dead_code(files)

        assert report.files_checked == 2
        unused_names = [e.export_name for e in report.unused_exports]
        assert "unusedHelper" in unused_names
        assert "usedHelper" not in unused_names

    @pytest.mark.asyncio
    async def test_detects_unused_import(self) -> None:
        """Import never used in the file → reported as unused."""
        from app.reliability.layer8_verification.dead_code_detector import (
            detect_dead_code,
        )

        files = {
            "src/App.tsx": """
import { useState, useEffect } from 'react';
export function App() {
    const [x, setX] = useState(0);
    return <div>{x}</div>;
}
""",
        }

        report = await detect_dead_code(files)

        unused_import_names = [i.import_name for i in report.unused_imports]
        assert "useEffect" in unused_import_names
        # useState is used, so it should NOT be in unused
        assert "useState" not in unused_import_names

    @pytest.mark.asyncio
    async def test_no_dead_code(self) -> None:
        """All exports used → no reports."""
        from app.reliability.layer8_verification.dead_code_detector import (
            detect_dead_code,
        )

        files = {
            "src/utils.ts": "export function helper() { return 1; }",
            "src/App.tsx": "import { helper } from './utils';\nconsole.log(helper());",
        }

        report = await detect_dead_code(files)

        assert report.files_checked == 2
        # helper is imported so shouldn't be reported as unused
        unused_names = [e.export_name for e in report.unused_exports]
        assert "helper" not in unused_names

    @pytest.mark.asyncio
    async def test_handles_empty_files(self) -> None:
        """Empty file dict → error message."""
        from app.reliability.layer8_verification.dead_code_detector import (
            detect_dead_code,
        )

        report = await detect_dead_code({})
        assert report.error is not None

    @pytest.mark.asyncio
    async def test_skips_non_ts_js_files(self) -> None:
        """Non TS/JS files skipped."""
        from app.reliability.layer8_verification.dead_code_detector import (
            detect_dead_code,
        )

        files = {
            "src/styles.css": "body { margin: 0; }",
            "README.md": "# Hello",
        }

        report = await detect_dead_code(files)
        assert report.files_checked == 0

    @pytest.mark.asyncio
    async def test_handles_export_list_syntax(self) -> None:
        """Handles export { name1, name2 } syntax."""
        from app.reliability.layer8_verification.dead_code_detector import (
            detect_dead_code,
        )

        files = {
            "src/helpers.ts": """
function foo() { return 1; }
function bar() { return 2; }
export { foo, bar };
""",
            "src/main.ts": "import { foo } from './helpers';\nconsole.log(foo());",
        }

        report = await detect_dead_code(files)
        unused_names = [e.export_name for e in report.unused_exports]
        assert "bar" in unused_names
        assert "foo" not in unused_names

    @pytest.mark.asyncio
    async def test_handles_default_export(self) -> None:
        """Default exports handled correctly."""
        from app.reliability.layer8_verification.dead_code_detector import (
            detect_dead_code,
        )

        files = {
            "src/Component.tsx": "export default function MyComponent() { return <div />; }",
            "src/App.tsx": "import MyComponent from './Component';\nexport default function App() { return <MyComponent />; }",
        }

        report = await detect_dead_code(files)
        # Default exports shouldn't be in unused (we skip them)
        unused_names = [e.export_name for e in report.unused_exports]
        assert "default" not in unused_names


# =====================================================================
# 6. SEED GENERATOR TESTS
# =====================================================================


class TestSeedGenerator:
    """Tests for seed_generator.py."""

    SAMPLE_SCHEMA = """
CREATE TABLE users (
    id UUID PRIMARY KEY,
    email VARCHAR(255) NOT NULL UNIQUE,
    username VARCHAR(100) NOT NULL UNIQUE,
    first_name VARCHAR(100),
    last_name VARCHAR(100),
    password_hash TEXT NOT NULL,
    avatar_url TEXT,
    role VARCHAR(20) DEFAULT 'user',
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE projects (
    id UUID PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES users(id),
    title VARCHAR(256) NOT NULL,
    description TEXT,
    status VARCHAR(20) DEFAULT 'active',
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE tasks (
    id UUID PRIMARY KEY,
    project_id UUID NOT NULL REFERENCES projects(id),
    title VARCHAR(256) NOT NULL,
    description TEXT,
    priority VARCHAR(20) DEFAULT 'medium',
    status VARCHAR(20) DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT NOW()
);
"""

    @pytest.mark.asyncio
    async def test_generates_seed_data(self) -> None:
        """Generates seed data for all tables."""
        from app.reliability.layer8_verification.seed_generator import (
            generate_and_apply_seeds,
        )

        report = await generate_and_apply_seeds(
            db_schema=self.SAMPLE_SCHEMA,
            tech_stack="fastapi_react",
        )

        assert len(report.tables_seeded) == 3
        assert "users" in report.tables_seeded
        assert "projects" in report.tables_seeded
        assert "tasks" in report.tables_seeded
        assert report.records_created > 0

    @pytest.mark.asyncio
    async def test_respects_fk_order(self) -> None:
        """Users seeded before projects, projects before tasks."""
        from app.reliability.layer8_verification.seed_generator import (
            generate_and_apply_seeds,
        )

        report = await generate_and_apply_seeds(
            db_schema=self.SAMPLE_SCHEMA,
            tech_stack="nextjs",
        )

        # FK order: users → projects → tasks
        idx_users = report.tables_seeded.index("users")
        idx_projects = report.tables_seeded.index("projects")
        idx_tasks = report.tables_seeded.index("tasks")
        assert idx_users < idx_projects < idx_tasks

    @pytest.mark.asyncio
    async def test_generates_realistic_users(self) -> None:
        """User seed data has realistic names and emails."""
        from app.reliability.layer8_verification.seed_generator import (
            generate_and_apply_seeds,
        )

        report = await generate_and_apply_seeds(
            db_schema=self.SAMPLE_SCHEMA,
            tech_stack="fastapi_react",
        )

        users = report.seed_data.get("users", [])
        assert len(users) == 10  # 10 users as specified

        for user in users:
            assert "email" in user
            assert "username" in user
            assert "@" in str(user["email"])

    @pytest.mark.asyncio
    async def test_generates_sql_statements(self) -> None:
        """SQL INSERT statements are generated."""
        from app.reliability.layer8_verification.seed_generator import (
            generate_and_apply_seeds,
        )

        report = await generate_and_apply_seeds(
            db_schema=self.SAMPLE_SCHEMA,
            tech_stack="nextjs",
        )

        assert len(report.sql_statements) > 0
        # All statements should be INSERT
        for stmt in report.sql_statements:
            assert stmt.startswith("INSERT INTO")

    @pytest.mark.asyncio
    async def test_fk_references_valid(self) -> None:
        """FK values reference actual parent record IDs."""
        from app.reliability.layer8_verification.seed_generator import (
            generate_and_apply_seeds,
        )

        report = await generate_and_apply_seeds(
            db_schema=self.SAMPLE_SCHEMA,
            tech_stack="fastapi_react",
        )

        user_ids = {u["id"] for u in report.seed_data.get("users", [])}
        project_ids = {p["id"] for p in report.seed_data.get("projects", [])}

        for project in report.seed_data.get("projects", []):
            assert project["user_id"] in user_ids

        for task in report.seed_data.get("tasks", []):
            assert task["project_id"] in project_ids

    @pytest.mark.asyncio
    async def test_empty_schema_error(self) -> None:
        """Empty schema → error."""
        from app.reliability.layer8_verification.seed_generator import (
            generate_and_apply_seeds,
        )

        report = await generate_and_apply_seeds(
            db_schema="",
            tech_stack="nextjs",
        )

        assert len(report.errors) > 0

    @pytest.mark.asyncio
    async def test_unique_emails(self) -> None:
        """Generated emails are unique (as required by UNIQUE constraint)."""
        from app.reliability.layer8_verification.seed_generator import (
            generate_and_apply_seeds,
        )

        report = await generate_and_apply_seeds(
            db_schema=self.SAMPLE_SCHEMA,
            tech_stack="fastapi_react",
        )

        users = report.seed_data.get("users", [])
        emails = [u["email"] for u in users]
        assert len(emails) == len(set(emails))  # All unique

    @pytest.mark.asyncio
    async def test_handles_self_referencing_fk(self) -> None:
        """Tables with self-referencing FKs don't cause infinite loops."""
        from app.reliability.layer8_verification.seed_generator import (
            generate_and_apply_seeds,
        )

        schema = """
CREATE TABLE categories (
    id UUID PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    parent_id UUID REFERENCES categories(id)
);
"""

        report = await generate_and_apply_seeds(
            db_schema=schema,
            tech_stack="nextjs",
        )

        assert "categories" in report.tables_seeded
        assert report.records_created > 0

    @pytest.mark.asyncio
    async def test_schema_parser_handles_constraints(self) -> None:
        """Parser handles table-level constraints correctly."""
        from app.reliability.layer8_verification.seed_generator import (
            _parse_schema,
        )

        schema = """
CREATE TABLE orders (
    id UUID PRIMARY KEY,
    user_id UUID NOT NULL,
    total DECIMAL(10, 2),
    status VARCHAR(20) DEFAULT 'pending',
    CONSTRAINT fk_user FOREIGN KEY (user_id) REFERENCES users(id)
);
"""

        tables = _parse_schema(schema)
        assert len(tables) == 1
        assert tables[0].name == "orders"
        assert "user_id" in tables[0].foreign_keys

    @pytest.mark.asyncio
    async def test_deterministic_output(self) -> None:
        """Same schema + seed = same output (Faker.seed(42))."""
        from app.reliability.layer8_verification.seed_generator import (
            generate_and_apply_seeds,
        )

        report1 = await generate_and_apply_seeds(
            db_schema=self.SAMPLE_SCHEMA,
            tech_stack="fastapi_react",
        )
        report2 = await generate_and_apply_seeds(
            db_schema=self.SAMPLE_SCHEMA,
            tech_stack="fastapi_react",
        )

        # Same number of records
        assert report1.records_created == report2.records_created
        assert report1.tables_seeded == report2.tables_seeded


# =====================================================================
# INTEGRATION: All modules importable
# =====================================================================


class TestLayer8Integration:
    """Verify all Layer 8 modules are importable and exports are correct."""

    def test_all_exports_importable(self) -> None:
        """All __all__ exports are available."""
        from app.reliability.layer8_verification import (
            A11yReport,
            DeadCodeReport,
            Finding,
            PerfReport,
            SASTReport,
            SeedReport,
            VisualRegressionReport,
            detect_dead_code,
            generate_and_apply_seeds,
            run_a11y_audit,
            run_perf_audit,
            run_sast_scan,
            run_visual_regression,
        )

        # All should be non-None
        assert A11yReport is not None
        assert DeadCodeReport is not None
        assert Finding is not None
        assert PerfReport is not None
        assert SASTReport is not None
        assert SeedReport is not None
        assert VisualRegressionReport is not None
        assert detect_dead_code is not None
        assert generate_and_apply_seeds is not None
        assert run_a11y_audit is not None
        assert run_perf_audit is not None
        assert run_sast_scan is not None
        assert run_visual_regression is not None

    def test_report_defaults(self) -> None:
        """All reports have sane defaults."""
        from app.reliability.layer8_verification import (
            A11yReport,
            DeadCodeReport,
            PerfReport,
            SASTReport,
            SeedReport,
            VisualRegressionReport,
        )

        assert VisualRegressionReport().passed is True
        assert SASTReport().passed is True
        assert PerfReport().passed is True
        assert A11yReport().passed is True
        assert DeadCodeReport().files_checked == 0
        assert SeedReport().records_created == 0

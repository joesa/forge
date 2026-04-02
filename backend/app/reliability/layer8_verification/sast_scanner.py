"""
Layer 8 — Static Application Security Testing (SAST) scanner.

Runs Semgrep with security-focused rulesets and detect-secrets to find
hardcoded credentials.  Critical/High severity findings cause Gate G11
failure.

Rulesets applied (based on detected tech stack):
  - python.django.security (if Python)
  - javascript.react.security
  - javascript.express.security
  - generic.secrets (no hardcoded API keys)
"""

from __future__ import annotations

import asyncio
import json
import re
import tempfile
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

import structlog

logger = structlog.get_logger(__name__)


# ── Types ────────────────────────────────────────────────────────────


class Severity(str, Enum):
    """Finding severity levels."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


@dataclass
class Finding:
    """A single SAST finding."""

    rule_id: str
    severity: Severity
    message: str
    file_path: str
    line_number: int
    code_snippet: str = ""
    category: str = "security"


@dataclass
class SASTReport:
    """Full SAST scan report."""

    passed: bool = True
    findings: list[Finding] = field(default_factory=list)
    severity_counts: dict[str, int] = field(default_factory=dict)
    files_scanned: int = 0
    error: str | None = None


# ── Built-in pattern scanners ───────────────────────────────────────

# Patterns that detect hardcoded secrets
SECRET_PATTERNS: list[tuple[str, str]] = [
    (r"(?i)(api[_-]?key|apikey)\s*[:=]\s*['\"][A-Za-z0-9_\-]{16,}['\"]",
     "Hardcoded API key detected"),
    (r"(?i)(secret[_-]?key|secretkey)\s*[:=]\s*['\"][A-Za-z0-9_\-]{16,}['\"]",
     "Hardcoded secret key detected"),
    (r"(?i)(password|passwd|pwd)\s*[:=]\s*['\"][^'\"]{8,}['\"]",
     "Hardcoded password detected"),
    (r"(?i)(access[_-]?token|auth[_-]?token)\s*[:=]\s*['\"][A-Za-z0-9_\-\.]{16,}['\"]",
     "Hardcoded access token detected"),
    (r"(?i)aws[_-]?secret[_-]?access[_-]?key\s*[:=]\s*['\"][A-Za-z0-9/+=]{20,}['\"]",
     "Hardcoded AWS secret key"),
    (r"sk-[A-Za-z0-9]{20,}",
     "OpenAI API key detected"),
    (r"sk_live_[A-Za-z0-9]{20,}",
     "Stripe live secret key detected"),
    (r"sk_test_[A-Za-z0-9]{20,}",
     "Stripe test secret key detected"),
    (r"ghp_[A-Za-z0-9]{36,}",
     "GitHub personal access token detected"),
    (r"-----BEGIN\s+(RSA\s+)?PRIVATE\s+KEY-----",
     "Private key embedded in source"),
]

# React security patterns
REACT_SECURITY_PATTERNS: list[tuple[str, str, Severity]] = [
    (r"dangerouslySetInnerHTML",
     "dangerouslySetInnerHTML usage — potential XSS vector",
     Severity.HIGH),
    (r"eval\s*\(",
     "eval() usage — code injection risk",
     Severity.CRITICAL),
    (r"document\.write\s*\(",
     "document.write() — DOM-based XSS risk",
     Severity.HIGH),
    (r"innerHTML\s*=",
     "Direct innerHTML assignment — XSS risk",
     Severity.HIGH),
    (r"window\.location\s*=\s*[^;]*\+",
     "Dynamic URL construction — open redirect risk",
     Severity.MEDIUM),
]

# Express/Node security patterns
EXPRESS_SECURITY_PATTERNS: list[tuple[str, str, Severity]] = [
    (r"app\.use\s*\(\s*cors\s*\(\s*\)\s*\)",
     "CORS enabled with no origin restriction",
     Severity.MEDIUM),
    (r"child_process\.(exec|spawn)\s*\([^)]*\+",
     "Command injection — dynamic shell command construction",
     Severity.CRITICAL),
    (r"\.query\s*\([^)]*\+",
     "SQL injection — string concatenation in query",
     Severity.CRITICAL),
    (r"new\s+Function\s*\(",
     "Dynamic function construction — code injection risk",
     Severity.HIGH),
]

# Python/Django security patterns
PYTHON_SECURITY_PATTERNS: list[tuple[str, str, Severity]] = [
    (r"os\.system\s*\(",
     "os.system() — command injection risk, use subprocess with shell=False",
     Severity.HIGH),
    (r"subprocess\.(?:call|run|Popen)\s*\([^)]*shell\s*=\s*True",
     "subprocess with shell=True — command injection risk",
     Severity.HIGH),
    (r"pickle\.loads?\s*\(",
     "pickle.load(s) — deserialization of untrusted data",
     Severity.HIGH),
    (r"yaml\.load\s*\([^)]*(?!Loader)",
     "yaml.load without safe Loader — arbitrary code execution",
     Severity.CRITICAL),
    (r"exec\s*\(",
     "exec() usage — code injection risk",
     Severity.CRITICAL),
    (r"__import__\s*\(",
     "Dynamic import — potential code injection",
     Severity.MEDIUM),
]

# File extensions to language mapping
EXTENSION_TO_LANGUAGE: dict[str, str] = {
    ".py": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".mjs": "javascript",
    ".cjs": "javascript",
}


# ── Internal scan helpers ───────────────────────────────────────────


def _detect_file_language(file_path: str) -> str:
    """Detect language from file extension."""
    ext = Path(file_path).suffix.lower()
    return EXTENSION_TO_LANGUAGE.get(ext, "unknown")


def _scan_secrets(
    file_path: str,
    content: str,
    findings: list[Finding],
) -> None:
    """Scan a single file for hardcoded secrets."""
    for line_num, line in enumerate(content.split("\n"), 1):
        # Skip comments and obviously test/example values
        stripped = line.strip()
        if stripped.startswith(("#", "//", "/*", "*")):
            continue

        for pattern, message in SECRET_PATTERNS:
            matches = re.finditer(pattern, line)
            for match in matches:
                # Skip common false positives
                snippet = match.group()
                lower_snippet = snippet.lower()
                if any(
                    fp in lower_snippet
                    for fp in [
                        "example", "placeholder", "your_", "xxx",
                        "changeme", "todo", "fixme", "test-",
                        "process.env", "os.environ", "settings.",
                    ]
                ):
                    continue

                findings.append(Finding(
                    rule_id="generic.secrets.hardcoded",
                    severity=Severity.CRITICAL,
                    message=message,
                    file_path=file_path,
                    line_number=line_num,
                    code_snippet=line.strip()[:200],
                    category="secrets",
                ))


def _scan_patterns(
    file_path: str,
    content: str,
    patterns: list[tuple[str, str, Severity]],
    findings: list[Finding],
    ruleset_prefix: str,
) -> None:
    """Scan a file against a list of regex patterns."""
    for line_num, line in enumerate(content.split("\n"), 1):
        stripped = line.strip()
        # Skip comments
        if stripped.startswith(("#", "//", "/*", "*")):
            continue

        for pattern, message, severity in patterns:
            if re.search(pattern, line):
                findings.append(Finding(
                    rule_id=f"{ruleset_prefix}.{pattern[:30]}",
                    severity=severity,
                    message=message,
                    file_path=file_path,
                    line_number=line_num,
                    code_snippet=stripped[:200],
                ))


async def _try_semgrep(
    files_dir: str,
    rulesets: list[str],
) -> list[Finding]:
    """
    Try to run Semgrep CLI on the given directory.

    Returns findings if Semgrep is available, empty list otherwise.
    Falls back to built-in patterns (which is the common case during
    build pipeline execution where Semgrep may not be installed).
    """
    findings: list[Finding] = []

    try:
        rules_arg = " ".join(f"--config=p/{r}" for r in rulesets)
        cmd = (
            f"semgrep --json --quiet {rules_arg} "
            f"--no-git-ignore {files_dir}"
        )

        process = await asyncio.create_subprocess_shell(
            cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(
            process.communicate(), timeout=120
        )

        if stdout:
            result = json.loads(stdout.decode())
            for finding in result.get("results", []):
                sev_str = finding.get("extra", {}).get(
                    "severity", "info"
                ).lower()
                try:
                    severity = Severity(sev_str)
                except ValueError:
                    severity = Severity.INFO

                findings.append(Finding(
                    rule_id=finding.get("check_id", "unknown"),
                    severity=severity,
                    message=finding.get("extra", {}).get(
                        "message", "Security finding"
                    ),
                    file_path=finding.get("path", "unknown"),
                    line_number=finding.get("start", {}).get("line", 0),
                    code_snippet=finding.get("extra", {}).get(
                        "lines", ""
                    )[:200],
                ))

    except FileNotFoundError:
        logger.info("semgrep_not_installed", msg="Falling back to built-in patterns")
    except asyncio.TimeoutError:
        logger.warning("semgrep_timeout", msg="Semgrep timed out after 120s")
    except Exception as exc:
        logger.warning("semgrep_error", error=str(exc))

    return findings


async def _try_detect_secrets(files_dir: str) -> list[Finding]:
    """
    Try to run detect-secrets CLI on the given directory.

    Returns findings if detect-secrets is available, empty list otherwise.
    """
    findings: list[Finding] = []

    try:
        cmd = f"detect-secrets scan {files_dir} --json"

        process = await asyncio.create_subprocess_shell(
            cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(
            process.communicate(), timeout=60
        )

        if stdout:
            result = json.loads(stdout.decode())
            for file_path, secrets in result.get("results", {}).items():
                for secret in secrets:
                    findings.append(Finding(
                        rule_id=f"detect-secrets.{secret.get('type', 'unknown')}",
                        severity=Severity.CRITICAL,
                        message=f"Detected secret: {secret.get('type', 'unknown')}",
                        file_path=file_path,
                        line_number=secret.get("line_number", 0),
                        category="secrets",
                    ))

    except FileNotFoundError:
        logger.info(
            "detect_secrets_not_installed",
            msg="Falling back to built-in secret patterns",
        )
    except asyncio.TimeoutError:
        logger.warning("detect_secrets_timeout")
    except Exception as exc:
        logger.warning("detect_secrets_error", error=str(exc))

    return findings


# ── Public API ──────────────────────────────────────────────────────


async def run_sast_scan(
    generated_files: dict[str, str],
) -> SASTReport:
    """
    Run SAST analysis on the generated files.

    Parameters
    ----------
    generated_files : dict[str, str]
        Mapping of file paths to file contents.

    Returns
    -------
    SASTReport
        Report with all findings and pass/fail status.
        Gate G11 fails on any Critical or High findings.
    """
    report = SASTReport()

    if not generated_files:
        report.error = "No files provided for scanning"
        report.passed = False
        return report

    all_findings: list[Finding] = []

    try:
        # Detect which rulesets apply based on file types
        has_python = False
        has_js_ts = False

        for file_path in generated_files:
            lang = _detect_file_language(file_path)
            if lang == "python":
                has_python = True
            elif lang in ("javascript", "typescript"):
                has_js_ts = True

        # Write files to a temp directory for external tool scanning
        with tempfile.TemporaryDirectory(prefix="forge_sast_") as tmpdir:
            for file_path, content in generated_files.items():
                target = Path(tmpdir) / file_path.lstrip("/")
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(content, encoding="utf-8")
                report.files_scanned += 1

            # Try external tools first
            semgrep_rulesets: list[str] = ["generic.secrets"]
            if has_js_ts:
                semgrep_rulesets.extend([
                    "javascript.react.security",
                    "javascript.express.security",
                ])
            if has_python:
                semgrep_rulesets.append("python.django.security")

            semgrep_findings = await _try_semgrep(tmpdir, semgrep_rulesets)
            all_findings.extend(semgrep_findings)

            detect_secrets_findings = await _try_detect_secrets(tmpdir)
            all_findings.extend(detect_secrets_findings)

        # Always run built-in pattern scanners (complementary to external tools)
        for file_path, content in generated_files.items():
            # Secret detection (built-in)
            _scan_secrets(file_path, content, all_findings)

            lang = _detect_file_language(file_path)

            # Language-specific patterns
            if lang in ("javascript", "typescript"):
                _scan_patterns(
                    file_path, content,
                    REACT_SECURITY_PATTERNS,
                    all_findings,
                    "react.security",
                )
                _scan_patterns(
                    file_path, content,
                    EXPRESS_SECURITY_PATTERNS,
                    all_findings,
                    "express.security",
                )
            elif lang == "python":
                _scan_patterns(
                    file_path, content,
                    PYTHON_SECURITY_PATTERNS,
                    all_findings,
                    "python.security",
                )

        # Deduplicate findings by (file, line, rule)
        seen: set[tuple[str, int, str]] = set()
        unique_findings: list[Finding] = []
        for f in all_findings:
            key = (f.file_path, f.line_number, f.rule_id)
            if key not in seen:
                seen.add(key)
                unique_findings.append(f)

        report.findings = unique_findings

        # Count severities
        for severity in Severity:
            count = sum(
                1 for f in report.findings if f.severity == severity
            )
            if count > 0:
                report.severity_counts[severity.value] = count

        # Gate G11: Critical or High = failure
        blocking_count = sum(
            1
            for f in report.findings
            if f.severity in (Severity.CRITICAL, Severity.HIGH)
        )
        report.passed = blocking_count == 0

        logger.info(
            "sast_scan_complete",
            files_scanned=report.files_scanned,
            total_findings=len(report.findings),
            blocking=blocking_count,
            passed=report.passed,
        )

    except Exception as exc:
        report.passed = False
        report.error = str(exc)
        logger.error("sast_scan_failed", error=str(exc))

    return report

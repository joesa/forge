"""
Layer 9 — Migration safety checker.

Scans SQL migration text for destructive operations and blocks them
before they reach the database.  Called by DBAgent before writing
migration files.

Blocked operations:
  - DROP TABLE: always blocked
  - DROP COLUMN: blocked if column has data (contextual)
  - ALTER COLUMN type change: warning (potential data loss)
  - DELETE without WHERE: always blocked
  - TRUNCATE TABLE: always blocked

Returns a SafetyReport with detailed analysis and blocking decisions.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum

import structlog

logger = structlog.get_logger(__name__)


# ── Types ────────────────────────────────────────────────────────────


class OpSeverity(str, Enum):
    """Severity of a destructive operation."""

    BLOCK = "block"  # Operation must not proceed
    WARN = "warn"  # Operation is risky but allowed


class OpType(str, Enum):
    """Types of destructive SQL operations."""

    DROP_TABLE = "drop_table"
    DROP_COLUMN = "drop_column"
    ALTER_COLUMN_TYPE = "alter_column_type"
    DELETE_WITHOUT_WHERE = "delete_without_where"
    TRUNCATE_TABLE = "truncate_table"
    DROP_INDEX = "drop_index"
    DROP_CONSTRAINT = "drop_constraint"
    RENAME_TABLE = "rename_table"
    RENAME_COLUMN = "rename_column"


@dataclass
class DestructiveOp:
    """A single detected destructive operation."""

    op_type: OpType
    severity: OpSeverity
    description: str
    sql_snippet: str
    line_number: int = 0
    table_name: str = ""
    column_name: str = ""


@dataclass
class SafetyReport:
    """Full migration safety analysis."""

    safe: bool = True
    destructive_ops: list[DestructiveOp] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    statements_analyzed: int = 0
    error: str | None = None


# ── Pattern definitions ──────────────────────────────────────────────

# Each pattern: (compiled regex, OpType, OpSeverity, description_template)
# Description templates use {table} and {column} placeholders.

_DROP_TABLE_RE = re.compile(
    r"\bDROP\s+TABLE\s+(?:IF\s+EXISTS\s+)?[`\"']?(\w+)[`\"']?",
    re.IGNORECASE,
)

_DROP_COLUMN_RE = re.compile(
    r"\bALTER\s+TABLE\s+[`\"']?(\w+)[`\"']?\s+"
    r"DROP\s+(?:COLUMN\s+)?(?:IF\s+EXISTS\s+)?[`\"']?(\w+)[`\"']?",
    re.IGNORECASE,
)

_ALTER_COLUMN_TYPE_RE = re.compile(
    r"\bALTER\s+TABLE\s+[`\"']?(\w+)[`\"']?\s+"
    r"ALTER\s+(?:COLUMN\s+)?[`\"']?(\w+)[`\"']?\s+"
    r"(?:SET\s+DATA\s+)?TYPE\s+(\w+)",
    re.IGNORECASE,
)

_DELETE_WITHOUT_WHERE_RE = re.compile(
    r"\bDELETE\s+FROM\s+[`\"']?(\w+)[`\"']?\s*;",
    re.IGNORECASE,
)

_TRUNCATE_RE = re.compile(
    r"\bTRUNCATE\s+(?:TABLE\s+)?[`\"']?(\w+)[`\"']?",
    re.IGNORECASE,
)

_DROP_INDEX_RE = re.compile(
    r"\bDROP\s+INDEX\s+(?:IF\s+EXISTS\s+)?(?:CONCURRENTLY\s+)?[`\"']?(\w+)[`\"']?",
    re.IGNORECASE,
)

_DROP_CONSTRAINT_RE = re.compile(
    r"\bALTER\s+TABLE\s+[`\"']?(\w+)[`\"']?\s+"
    r"DROP\s+CONSTRAINT\s+(?:IF\s+EXISTS\s+)?[`\"']?(\w+)[`\"']?",
    re.IGNORECASE,
)

_RENAME_TABLE_RE = re.compile(
    r"\bALTER\s+TABLE\s+[`\"']?(\w+)[`\"']?\s+"
    r"RENAME\s+TO\s+[`\"']?(\w+)[`\"']?",
    re.IGNORECASE,
)

_RENAME_COLUMN_RE = re.compile(
    r"\bALTER\s+TABLE\s+[`\"']?(\w+)[`\"']?\s+"
    r"RENAME\s+(?:COLUMN\s+)?[`\"']?(\w+)[`\"']?\s+"
    r"TO\s+[`\"']?(\w+)[`\"']?",
    re.IGNORECASE,
)


# ── Scanner ──────────────────────────────────────────────────────────


def _scan_migration(sql: str) -> list[DestructiveOp]:
    """Scan SQL text for destructive operations."""
    ops: list[DestructiveOp] = []

    for line_num, line in enumerate(sql.split("\n"), 1):
        stripped = line.strip()
        # Skip comments
        if stripped.startswith("--") or stripped.startswith("/*"):
            continue

        # DROP TABLE — always block
        for match in _DROP_TABLE_RE.finditer(line):
            table = match.group(1)
            ops.append(DestructiveOp(
                op_type=OpType.DROP_TABLE,
                severity=OpSeverity.BLOCK,
                description=f"DROP TABLE {table} — all data will be lost",
                sql_snippet=stripped[:200],
                line_number=line_num,
                table_name=table,
            ))

        # DROP COLUMN — block (may contain data)
        for match in _DROP_COLUMN_RE.finditer(line):
            table = match.group(1)
            column = match.group(2)
            ops.append(DestructiveOp(
                op_type=OpType.DROP_COLUMN,
                severity=OpSeverity.BLOCK,
                description=(
                    f"DROP COLUMN {column} from {table} — "
                    f"column data will be lost"
                ),
                sql_snippet=stripped[:200],
                line_number=line_num,
                table_name=table,
                column_name=column,
            ))

        # ALTER COLUMN TYPE — warn
        for match in _ALTER_COLUMN_TYPE_RE.finditer(line):
            table = match.group(1)
            column = match.group(2)
            new_type = match.group(3)
            ops.append(DestructiveOp(
                op_type=OpType.ALTER_COLUMN_TYPE,
                severity=OpSeverity.WARN,
                description=(
                    f"ALTER COLUMN {column} in {table} to {new_type} — "
                    f"may cause data loss during type conversion"
                ),
                sql_snippet=stripped[:200],
                line_number=line_num,
                table_name=table,
                column_name=column,
            ))

        # DELETE without WHERE — always block
        for match in _DELETE_WITHOUT_WHERE_RE.finditer(line):
            table = match.group(1)
            ops.append(DestructiveOp(
                op_type=OpType.DELETE_WITHOUT_WHERE,
                severity=OpSeverity.BLOCK,
                description=(
                    f"DELETE FROM {table} without WHERE clause — "
                    f"all rows will be deleted"
                ),
                sql_snippet=stripped[:200],
                line_number=line_num,
                table_name=table,
            ))

        # TRUNCATE — always block
        for match in _TRUNCATE_RE.finditer(line):
            table = match.group(1)
            ops.append(DestructiveOp(
                op_type=OpType.TRUNCATE_TABLE,
                severity=OpSeverity.BLOCK,
                description=f"TRUNCATE TABLE {table} — all data will be deleted",
                sql_snippet=stripped[:200],
                line_number=line_num,
                table_name=table,
            ))

        # DROP INDEX — warn (data safe, but may affect performance)
        for match in _DROP_INDEX_RE.finditer(line):
            index_name = match.group(1)
            ops.append(DestructiveOp(
                op_type=OpType.DROP_INDEX,
                severity=OpSeverity.WARN,
                description=(
                    f"DROP INDEX {index_name} — may impact query performance"
                ),
                sql_snippet=stripped[:200],
                line_number=line_num,
            ))

        # DROP CONSTRAINT — warn
        for match in _DROP_CONSTRAINT_RE.finditer(line):
            table = match.group(1)
            constraint = match.group(2)
            ops.append(DestructiveOp(
                op_type=OpType.DROP_CONSTRAINT,
                severity=OpSeverity.WARN,
                description=(
                    f"DROP CONSTRAINT {constraint} on {table} — "
                    f"may weaken data integrity"
                ),
                sql_snippet=stripped[:200],
                line_number=line_num,
                table_name=table,
            ))

        # RENAME TABLE — warn
        for match in _RENAME_TABLE_RE.finditer(line):
            old_name = match.group(1)
            new_name = match.group(2)
            ops.append(DestructiveOp(
                op_type=OpType.RENAME_TABLE,
                severity=OpSeverity.WARN,
                description=(
                    f"RENAME TABLE {old_name} to {new_name} — "
                    f"may break application references"
                ),
                sql_snippet=stripped[:200],
                line_number=line_num,
                table_name=old_name,
            ))

        # RENAME COLUMN — warn
        for match in _RENAME_COLUMN_RE.finditer(line):
            table = match.group(1)
            old_col = match.group(2)
            new_col = match.group(3)
            ops.append(DestructiveOp(
                op_type=OpType.RENAME_COLUMN,
                severity=OpSeverity.WARN,
                description=(
                    f"RENAME COLUMN {old_col} to {new_col} in {table} — "
                    f"may break application references"
                ),
                sql_snippet=stripped[:200],
                line_number=line_num,
                table_name=table,
                column_name=old_col,
            ))

    return ops


# ── Public API ───────────────────────────────────────────────────────


async def check_migration_safety(migration_sql: str) -> SafetyReport:
    """Analyze a SQL migration for destructive operations.

    Parameters
    ----------
    migration_sql : str
        The raw SQL migration text to analyze.

    Returns
    -------
    SafetyReport
        Report with safety status, detected operations, and warnings.
        ``safe`` is False if any BLOCK-severity operation is found.
    """
    report = SafetyReport()

    if not migration_sql or not migration_sql.strip():
        report.error = "Empty migration SQL provided"
        report.safe = False
        return report

    try:
        # Count statements (rough — split on semicolons)
        statements = [
            s.strip()
            for s in migration_sql.split(";")
            if s.strip() and not s.strip().startswith("--")
        ]
        report.statements_analyzed = len(statements)

        # Scan for destructive operations
        ops = _scan_migration(migration_sql)
        report.destructive_ops = ops

        # Build warnings list
        for op in ops:
            if op.severity == OpSeverity.WARN:
                report.warnings.append(op.description)

        # Determine safety: any BLOCK = unsafe
        blocking_ops = [
            op for op in ops if op.severity == OpSeverity.BLOCK
        ]
        report.safe = len(blocking_ops) == 0

        logger.info(
            "migration_safety.checked",
            statements=report.statements_analyzed,
            destructive_ops=len(ops),
            blocking_ops=len(blocking_ops),
            safe=report.safe,
        )

    except Exception as exc:
        report.safe = False
        report.error = str(exc)
        logger.error("migration_safety.failed", error=str(exc))

    return report

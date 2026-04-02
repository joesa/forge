"""
Layer 2 — Database type injector.

Parses SQL DDL schema from DBAgent output and generates TypeScript
interfaces matching every database table.  Injected into PageAgent
and ComponentAgent prompts to ensure frontend types match DB schema.
"""

from __future__ import annotations

import re
from typing import Any

import structlog

logger = structlog.get_logger(__name__)

# ── SQL → TypeScript type mapping ────────────────────────────────────

_SQL_TO_TS_MAP: dict[str, str] = {
    # Strings
    "varchar": "string",
    "character varying": "string",
    "char": "string",
    "character": "string",
    "text": "string",
    "citext": "string",
    "name": "string",
    # Numbers
    "integer": "number",
    "int": "number",
    "int4": "number",
    "int8": "number",
    "smallint": "number",
    "bigint": "number",
    "serial": "number",
    "bigserial": "number",
    "numeric": "number",
    "decimal": "number",
    "real": "number",
    "float": "number",
    "float4": "number",
    "float8": "number",
    "double precision": "number",
    "money": "number",
    # Booleans
    "boolean": "boolean",
    "bool": "boolean",
    # Dates
    "timestamp": "string",
    "timestamp with time zone": "string",
    "timestamp without time zone": "string",
    "timestamptz": "string",
    "date": "string",
    "time": "string",
    "timetz": "string",
    "interval": "string",
    # JSON
    "json": "Record<string, unknown>",
    "jsonb": "Record<string, unknown>",
    # UUID
    "uuid": "string",
    # Binary
    "bytea": "Uint8Array",
    # Arrays
    "array": "unknown[]",
    # Enum (handled separately)
    "enum": "string",
    # Special
    "inet": "string",
    "cidr": "string",
    "macaddr": "string",
    "tsvector": "string",
    "tsquery": "string",
    "point": "{ x: number; y: number }",
    "xml": "string",
}


def _to_pascal_case(name: str) -> str:
    """Convert snake_case to PascalCase."""
    return "".join(word.capitalize() for word in name.split("_") if word)


def _sql_type_to_ts(sql_type: str) -> str:
    """Map a SQL column type to a TypeScript type."""
    # Normalize
    clean = sql_type.strip().lower()

    # Handle array types (e.g., "text[]", "integer[]")
    if clean.endswith("[]"):
        base_type = clean[:-2]
        ts_base = _SQL_TO_TS_MAP.get(base_type, "unknown")
        return f"{ts_base}[]"

    # Handle varchar(n), char(n), numeric(p,s) etc.
    if "(" in clean:
        base_type = clean.split("(")[0].strip()
        return _SQL_TO_TS_MAP.get(base_type, "unknown")

    return _SQL_TO_TS_MAP.get(clean, "unknown")


# ── SQL DDL parser ───────────────────────────────────────────────────

_CREATE_TABLE_RE = re.compile(
    r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?(?:\"?(\w+)\"?\.)?\"?(\w+)\"?\s*\(",
    re.IGNORECASE,
)

_COLUMN_RE = re.compile(
    r"^\s*\"?(\w+)\"?\s+(.+?)\s*,?\s*$",
    re.IGNORECASE,
)

# SQL keywords that signal end of type definition
_SQL_CONSTRAINT_KEYWORDS = {
    "NOT", "NULL", "DEFAULT", "PRIMARY", "UNIQUE",
    "REFERENCES", "CHECK", "CONSTRAINT", "GENERATED",
    "ON", "CASCADE", "RESTRICT", "SET",
}

_ENUM_RE = re.compile(
    r"CREATE\s+TYPE\s+(?:\"?(\w+)\"?\.)?\"?(\w+)\"?\s+AS\s+ENUM\s*\(([^)]+)\)",
    re.IGNORECASE,
)


def _extract_column_type_and_nullable(remainder: str) -> tuple[str, bool]:
    """Extract SQL type and nullable flag from a column definition line.

    Given e.g. 'UUID NOT NULL' → ('UUID', False)
    Given e.g. 'VARCHAR(255) NOT NULL' → ('VARCHAR(255)', False)
    Given e.g. 'TEXT' → ('TEXT', True)
    Given e.g. 'TIMESTAMP WITH TIME ZONE NOT NULL' → ('TIMESTAMP WITH TIME ZONE', False)
    """
    upper = remainder.upper()
    is_nullable = "NOT NULL" not in upper

    # Known multi-word SQL types
    multi_word_types = [
        "TIMESTAMP WITH TIME ZONE",
        "TIMESTAMP WITHOUT TIME ZONE",
        "DOUBLE PRECISION",
        "CHARACTER VARYING",
    ]

    for mwt in multi_word_types:
        if upper.startswith(mwt):
            return mwt.lower(), is_nullable

    # Handle type with parens: VARCHAR(255), NUMERIC(10,2)
    if "(" in remainder:
        paren_end = remainder.index(")") + 1
        type_part = remainder[:paren_end].strip()
        # Check for trailing []
        rest_after_paren = remainder[paren_end:].lstrip()
        if rest_after_paren.startswith("[]"):
            type_part += "[]"
        return type_part, is_nullable

    # Split on spaces and take tokens until we hit a constraint keyword
    tokens = remainder.split()
    type_tokens: list[str] = []
    for token in tokens:
        if token.upper() in _SQL_CONSTRAINT_KEYWORDS:
            break
        # Check for array suffix
        if token.endswith("[]"):
            type_tokens.append(token)
            break
        type_tokens.append(token)

    col_type = " ".join(type_tokens) if type_tokens else remainder
    return col_type.strip().rstrip(","), is_nullable


def _parse_create_tables(sql: str) -> list[dict[str, Any]]:
    """Parse CREATE TABLE statements from SQL DDL and return table defs."""
    tables: list[dict[str, Any]] = []

    # Find all CREATE TABLE blocks
    remainder = sql
    for match in _CREATE_TABLE_RE.finditer(sql):
        table_name = match.group(2)
        start = match.end()

        # Find the closing paren
        depth = 1
        pos = start
        while pos < len(remainder) and depth > 0:
            if remainder[pos] == "(":
                depth += 1
            elif remainder[pos] == ")":
                depth -= 1
            pos += 1

        body = remainder[start:pos - 1] if pos > start else ""

        columns: list[dict[str, str]] = []
        for line in body.split("\n"):
            line = line.strip()
            if not line or line.startswith("--"):
                continue
            # Skip constraints
            upper = line.upper().lstrip()
            if any(
                upper.startswith(kw)
                for kw in ("PRIMARY", "FOREIGN", "UNIQUE", "CHECK", "CONSTRAINT", "INDEX")
            ):
                continue

            col_match = _COLUMN_RE.match(line)
            if col_match:
                col_name = col_match.group(1)
                col_remainder = col_match.group(2).strip()

                col_type, is_nullable = _extract_column_type_and_nullable(
                    col_remainder
                )

                columns.append({
                    "name": col_name,
                    "sql_type": col_type,
                    "nullable": str(is_nullable).lower(),
                })

        tables.append({
            "name": table_name,
            "columns": columns,
        })

    return tables


def _parse_enums(sql: str) -> dict[str, list[str]]:
    """Parse CREATE TYPE ... AS ENUM statements."""
    enums: dict[str, list[str]] = {}
    for match in _ENUM_RE.finditer(sql):
        enum_name = match.group(2)
        values_str = match.group(3)
        values = [
            v.strip().strip("'\"")
            for v in values_str.split(",")
            if v.strip()
        ]
        enums[enum_name] = values
    return enums


def generate_typescript_types(sql_schema: str) -> str:
    """Generate TypeScript interfaces from SQL DDL schema.

    Args:
        sql_schema: SQL DDL string from DBAgent output.

    Returns:
        TypeScript file content with interfaces matching DB tables.
    """
    lines: list[str] = [
        "// ═══════════════════════════════════════════════════════════════",
        "// AUTO-GENERATED by FORGE Layer 2 — DB Type Injector",
        "// DO NOT EDIT — regenerated on each build pipeline run",
        "// ═══════════════════════════════════════════════════════════════",
        "",
    ]

    # Parse enums
    enums = _parse_enums(sql_schema)
    for enum_name, values in sorted(enums.items()):
        ts_name = _to_pascal_case(enum_name)
        values_str = " | ".join(f'"{v}"' for v in values)
        lines.append(f"export type {ts_name} = {values_str};")
        lines.append("")

    # Parse tables
    tables = _parse_create_tables(sql_schema)

    if not tables:
        lines.append("// No CREATE TABLE statements found in SQL schema")
        lines.append("")

        result = "\n".join(lines)
        logger.info(
            "db_type_injector.generated",
            table_count=0,
            enum_count=len(enums),
            output_length=len(result),
        )
        return result

    for table in tables:
        table_name = table["name"]
        columns = table["columns"]
        interface_name = _to_pascal_case(table_name)

        lines.append(f"export interface {interface_name} {{")

        for col in columns:
            col_name = col["name"]
            ts_type = _sql_type_to_ts(col["sql_type"])
            is_nullable = col.get("nullable", "true") == "true"

            if is_nullable:
                lines.append(f"  {col_name}: {ts_type} | null;")
            else:
                lines.append(f"  {col_name}: {ts_type};")

        lines.append("}")
        lines.append("")

    # Generate a table name union
    if len(tables) > 1:
        table_names = [f'"{t["name"]}"' for t in tables]
        lines.append("// ── Table name union ──")
        lines.append(f"export type TableName = {' | '.join(table_names)};")
        lines.append("")

    result = "\n".join(lines)

    logger.info(
        "db_type_injector.generated",
        table_count=len(tables),
        enum_count=len(enums),
        output_length=len(result),
    )

    return result

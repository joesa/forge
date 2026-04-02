"""
Layer 5 — Type inference engine.

Converts Pydantic v2 model definitions and SQL DDL schemas to TypeScript
interfaces.  Handles nullable fields, arrays, enums, and nested models.

Used to guarantee frontend TypeScript types match backend data contracts.
"""

from __future__ import annotations

import re

from pydantic import BaseModel, Field

import structlog

logger = structlog.get_logger(__name__)


# ── Pydantic → TypeScript mapping ────────────────────────────────────

_PYDANTIC_TO_TS: dict[str, str] = {
    "str": "string",
    "string": "string",
    "int": "number",
    "integer": "number",
    "float": "number",
    "bool": "boolean",
    "boolean": "boolean",
    "datetime": "string",
    "date": "string",
    "time": "string",
    "UUID": "string",
    "uuid": "string",
    "uuid.UUID": "string",
    "Any": "unknown",
    "dict": "Record<string, unknown>",
    "Dict": "Record<string, unknown>",
    "bytes": "Uint8Array",
    "Decimal": "number",
    "EmailStr": "string",
    "HttpUrl": "string",
    "AnyUrl": "string",
}

# SQL → TypeScript (reusing patterns from Layer 2 db_type_injector)
_SQL_TO_TS: dict[str, str] = {
    "varchar": "string",
    "character varying": "string",
    "char": "string",
    "text": "string",
    "citext": "string",
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
    "double precision": "number",
    "boolean": "boolean",
    "bool": "boolean",
    "timestamp": "string",
    "timestamp with time zone": "string",
    "timestamp without time zone": "string",
    "timestamptz": "string",
    "date": "string",
    "time": "string",
    "json": "Record<string, unknown>",
    "jsonb": "Record<string, unknown>",
    "uuid": "string",
    "bytea": "Uint8Array",
    "inet": "string",
}


# ── Pydantic model parser ───────────────────────────────────────────

_CLASS_RE = re.compile(
    r"class\s+(\w+)\s*\(\s*BaseModel\s*\)\s*:",
    re.MULTILINE,
)

_FIELD_RE = re.compile(
    r"^\s{4}(\w+)\s*:\s*(.+?)(?:\s*=.*)?$",
    re.MULTILINE,
)

_OPTIONAL_RE = re.compile(
    r"Optional\[(.+)\]"
)
_UNION_NONE_RE = re.compile(
    r"(.+)\s*\|\s*None"
)
_LIST_RE = re.compile(
    r"(?:list|List)\[(.+)\]"
)
_DICT_RE = re.compile(
    r"(?:dict|Dict)\[(.+),\s*(.+)\]"
)


def _parse_pydantic_type(type_str: str) -> tuple[str, bool]:
    """Parse a Pydantic type annotation to TypeScript type + nullable flag.

    Returns (ts_type, is_nullable).
    """
    type_str = type_str.strip()
    is_nullable = False

    # Handle Optional[T]
    opt_match = _OPTIONAL_RE.match(type_str)
    if opt_match:
        type_str = opt_match.group(1).strip()
        is_nullable = True

    # Handle T | None
    union_match = _UNION_NONE_RE.match(type_str)
    if union_match:
        type_str = union_match.group(1).strip()
        is_nullable = True

    # Handle list[T]
    list_match = _LIST_RE.match(type_str)
    if list_match:
        inner = list_match.group(1).strip()
        inner_ts, _ = _parse_pydantic_type(inner)
        return f"{inner_ts}[]", is_nullable

    # Handle dict[K, V]
    dict_match = _DICT_RE.match(type_str)
    if dict_match:
        key_type = dict_match.group(1).strip()
        val_type = dict_match.group(2).strip()
        key_ts, _ = _parse_pydantic_type(key_type)
        val_ts, _ = _parse_pydantic_type(val_type)
        return f"Record<{key_ts}, {val_ts}>", is_nullable

    # Direct mapping
    ts_type = _PYDANTIC_TO_TS.get(type_str, type_str)

    return ts_type, is_nullable


def _parse_pydantic_models(source: str) -> list[dict[str, object]]:
    """Parse Pydantic v2 model definitions from source code.

    Returns list of model dicts with 'name' and 'fields'.
    """
    models: list[dict[str, object]] = []

    # Split source into blocks by class definition
    class_positions: list[tuple[int, str]] = []
    for match in _CLASS_RE.finditer(source):
        class_positions.append((match.start(), match.group(1)))

    for idx, (pos, class_name) in enumerate(class_positions):
        # Get class body (until next class or end of file)
        end_pos = (
            class_positions[idx + 1][0]
            if idx + 1 < len(class_positions)
            else len(source)
        )
        class_body = source[pos:end_pos]

        fields: list[dict[str, str]] = []
        for field_match in _FIELD_RE.finditer(class_body):
            field_name = field_match.group(1)
            field_type = field_match.group(2).strip()

            # Skip special attributes
            if field_name.startswith("_") or field_name == "model_config":
                continue
            # Skip class-level comments/docstrings
            if field_name in ("class", "def", "async"):
                continue

            # Remove Field() wrapper if present
            if "Field(" in field_type:
                # Extract just the type annotation before Field
                field_type = field_type.split("=")[0].strip()
                if field_type.endswith(","):
                    field_type = field_type[:-1].strip()

            fields.append({
                "name": field_name,
                "type": field_type,
            })

        models.append({
            "name": class_name,
            "fields": fields,
        })

    return models


# ── SQL DDL parser ───────────────────────────────────────────────────

_CREATE_TABLE_RE = re.compile(
    r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?(?:\"?\w+\"?\.)?\"?(\w+)\"?\s*\(",
    re.IGNORECASE,
)

_SQL_COLUMN_RE = re.compile(
    r"^\s*\"?(\w+)\"?\s+(.+?)\s*,?\s*$",
    re.IGNORECASE,
)

_SQL_CONSTRAINT_KEYWORDS = {
    "NOT", "NULL", "DEFAULT", "PRIMARY", "UNIQUE",
    "REFERENCES", "CHECK", "CONSTRAINT", "GENERATED",
    "ON", "CASCADE", "RESTRICT", "SET",
}

_ENUM_RE = re.compile(
    r"CREATE\s+TYPE\s+(?:\"?\w+\"?\.)?\"?(\w+)\"?\s+AS\s+ENUM\s*\(([^)]+)\)",
    re.IGNORECASE,
)


def _to_pascal_case(name: str) -> str:
    """Convert snake_case to PascalCase."""
    return "".join(word.capitalize() for word in name.split("_") if word)


def _parse_sql_column_type(remainder: str) -> tuple[str, bool]:
    """Extract SQL type and nullable flag from column definition."""
    upper = remainder.upper()
    is_nullable = "NOT NULL" not in upper

    # Handle array types
    if "[]" in remainder:
        base = remainder.split("[]")[0].strip().lower()
        ts_base = _SQL_TO_TS.get(base, "unknown")
        return f"{ts_base}[]", is_nullable

    # Handle type with parens (VARCHAR(255) etc.)
    clean = remainder.lower().strip()
    if "(" in clean:
        base = clean.split("(")[0].strip()
        ts_type = _SQL_TO_TS.get(base, "unknown")
        return ts_type, is_nullable

    # Extract type tokens before constraint keywords
    tokens = remainder.split()
    type_tokens: list[str] = []
    for token in tokens:
        if token.upper() in _SQL_CONSTRAINT_KEYWORDS:
            break
        type_tokens.append(token)

    col_type = " ".join(type_tokens).lower().strip().rstrip(",")
    ts_type = _SQL_TO_TS.get(col_type, "unknown")
    return ts_type, is_nullable


def _parse_sql_tables(sql: str) -> tuple[list[dict[str, object]], dict[str, list[str]]]:
    """Parse CREATE TABLE and ENUM statements from SQL DDL.

    Returns (tables, enums).
    """
    tables: list[dict[str, object]] = []
    enums: dict[str, list[str]] = {}

    # Parse enums
    for match in _ENUM_RE.finditer(sql):
        enum_name = match.group(1)
        values = [
            v.strip().strip("'\"")
            for v in match.group(2).split(",")
            if v.strip()
        ]
        enums[enum_name] = values

    # Parse tables
    for match in _CREATE_TABLE_RE.finditer(sql):
        table_name = match.group(1)
        start = match.end()

        # Find closing paren
        depth = 1
        pos = start
        while pos < len(sql) and depth > 0:
            if sql[pos] == "(":
                depth += 1
            elif sql[pos] == ")":
                depth -= 1
            pos += 1

        body = sql[start:pos - 1] if pos > start else ""

        columns: list[dict[str, str]] = []
        for line in body.split("\n"):
            line = line.strip()
            if not line or line.startswith("--"):
                continue
            upper = line.upper().lstrip()
            if any(upper.startswith(kw) for kw in (
                "PRIMARY", "FOREIGN", "UNIQUE", "CHECK", "CONSTRAINT", "INDEX"
            )):
                continue

            col_match = _SQL_COLUMN_RE.match(line)
            if col_match:
                col_name = col_match.group(1)
                col_remainder = col_match.group(2).strip()
                ts_type, is_nullable = _parse_sql_column_type(col_remainder)
                columns.append({
                    "name": col_name,
                    "ts_type": ts_type,
                    "nullable": str(is_nullable).lower(),
                })

        tables.append({"name": table_name, "columns": columns})

    return tables, enums


# ── Main entry point ─────────────────────────────────────────────────


def infer_typescript_types(
    python_pydantic_schemas: str = "",
    sql_schema: str = "",
) -> str:
    """Convert Pydantic v2 models and SQL DDL to TypeScript interfaces.

    Args:
        python_pydantic_schemas: Python source containing Pydantic models.
        sql_schema: SQL DDL string with CREATE TABLE / CREATE TYPE.

    Returns:
        TypeScript file content with interfaces and types.
    """
    lines: list[str] = [
        "// ═══════════════════════════════════════════════════════════════",
        "// AUTO-GENERATED by FORGE Layer 5 — Type Inference Engine",
        "// DO NOT EDIT — regenerated on each build pipeline run",
        "// ═══════════════════════════════════════════════════════════════",
        "",
    ]

    model_count = 0
    table_count = 0
    enum_count = 0

    # ── Pydantic models → TypeScript interfaces ──────────────────────
    if python_pydantic_schemas:
        models = _parse_pydantic_models(python_pydantic_schemas)

        if models:
            lines.append("// ── From Pydantic v2 Models ──")
            lines.append("")

        for model in models:
            model_name = str(model["name"])
            fields = model.get("fields", [])
            if not isinstance(fields, list):
                continue

            lines.append(f"export interface {model_name} {{")

            for field in fields:
                if not isinstance(field, dict):
                    continue
                field_name = str(field.get("name", ""))
                field_type = str(field.get("type", "unknown"))

                ts_type, is_nullable = _parse_pydantic_type(field_type)

                if is_nullable:
                    lines.append(f"  {field_name}: {ts_type} | null;")
                else:
                    lines.append(f"  {field_name}: {ts_type};")

            lines.append("}")
            lines.append("")
            model_count += 1

    # ── SQL DDL → TypeScript interfaces ──────────────────────────────
    if sql_schema:
        tables, enums = _parse_sql_tables(sql_schema)

        # Generate enums
        if enums:
            lines.append("// ── From SQL Enums ──")
            lines.append("")

        for enum_name, values in sorted(enums.items()):
            ts_name = _to_pascal_case(enum_name)
            values_str = " | ".join(f'"{v}"' for v in values)
            lines.append(f"export type {ts_name} = {values_str};")
            lines.append("")
            enum_count += 1

        # Generate table interfaces
        if tables:
            lines.append("// ── From SQL Tables ──")
            lines.append("")

        for table in tables:
            table_name = str(table["name"])
            columns = table.get("columns", [])
            if not isinstance(columns, list):
                continue

            interface_name = _to_pascal_case(table_name)
            lines.append(f"export interface {interface_name} {{")

            for col in columns:
                if not isinstance(col, dict):
                    continue
                col_name = str(col.get("name", ""))
                ts_type = str(col.get("ts_type", "unknown"))
                is_nullable = col.get("nullable", "true") == "true"

                if is_nullable:
                    lines.append(f"  {col_name}: {ts_type} | null;")
                else:
                    lines.append(f"  {col_name}: {ts_type};")

            lines.append("}")
            lines.append("")
            table_count += 1

    if not model_count and not table_count:
        lines.append("// No Pydantic models or SQL tables found")
        lines.append("")

    result = "\n".join(lines)

    logger.info(
        "type_inference_engine.completed",
        pydantic_models=model_count,
        sql_tables=table_count,
        sql_enums=enum_count,
        output_length=len(result),
    )

    return result

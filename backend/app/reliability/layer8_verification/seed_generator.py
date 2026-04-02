"""
Layer 8 — Seed data generator for sandbox databases.

Analyses a DB schema (SQL DDL) to understand tables, columns, foreign
keys, and constraints.  Generates realistic seed data using Faker,
respecting FK relationships (creates parent records before children).

Seed data characteristics:
  - Users: 10 realistic users with real-looking names/emails
  - Main entities: 5–20 records each with plausible values
  - Foreign keys resolved in dependency order
  - Unique constraints respected
  - Column-type-aware value generation
"""

from __future__ import annotations

import random
import re
from dataclasses import dataclass, field

import structlog
from faker import Faker

logger = structlog.get_logger(__name__)

fake = Faker()


# ── Schema analysis types ───────────────────────────────────────────


@dataclass
class ColumnInfo:
    """Parsed column information."""

    name: str
    data_type: str
    nullable: bool = True
    is_primary_key: bool = False
    is_unique: bool = False
    is_foreign_key: bool = False
    fk_table: str = ""
    fk_column: str = ""
    default: str | None = None
    max_length: int | None = None


@dataclass
class TableInfo:
    """Parsed table information."""

    name: str
    columns: list[ColumnInfo] = field(default_factory=list)
    primary_key: str = "id"
    foreign_keys: dict[str, tuple[str, str]] = field(default_factory=dict)


@dataclass
class SeedReport:
    """Seed generation report."""

    tables_seeded: list[str] = field(default_factory=list)
    records_created: int = 0
    seed_data: dict[str, list[dict[str, object]]] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    sql_statements: list[str] = field(default_factory=list)


# ── SQL Schema Parser ──────────────────────────────────────────────


def _parse_schema(schema_sql: str) -> list[TableInfo]:
    """
    Parse a SQL DDL schema and extract table/column information.

    Handles CREATE TABLE statements with column types, constraints,
    and foreign key references.
    """
    tables: list[TableInfo] = []

    # Find all CREATE TABLE blocks
    table_pattern = re.compile(
        r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?"
        r"[\"']?(\w+)[\"']?\s*\((.*?)\)\s*;",
        re.DOTALL | re.IGNORECASE,
    )

    for match in table_pattern.finditer(schema_sql):
        table_name = match.group(1).lower()
        body = match.group(2)
        table = TableInfo(name=table_name)

        # Split into column/constraint definitions
        # Handle nested parentheses in CHECK constraints
        depth = 0
        parts: list[str] = []
        current: list[str] = []
        for char in body:
            if char == "(":
                depth += 1
                current.append(char)
            elif char == ")":
                depth -= 1
                current.append(char)
            elif char == "," and depth == 0:
                parts.append("".join(current).strip())
                current = []
            else:
                current.append(char)
        if current:
            parts.append("".join(current).strip())

        for part in parts:
            part_stripped = part.strip()
            part_upper = part_stripped.upper()

            # Skip table-level constraints
            if part_upper.startswith(("PRIMARY KEY", "UNIQUE", "CHECK", "CONSTRAINT", "INDEX")):
                # But extract FK constraints
                fk_match = re.search(
                    r"FOREIGN\s+KEY\s*\([\"']?(\w+)[\"']?\)\s+"
                    r"REFERENCES\s+[\"']?(\w+)[\"']?\s*\([\"']?(\w+)[\"']?\)",
                    part_stripped, re.IGNORECASE,
                )
                if fk_match:
                    col_name = fk_match.group(1).lower()
                    ref_table = fk_match.group(2).lower()
                    ref_col = fk_match.group(3).lower()
                    table.foreign_keys[col_name] = (ref_table, ref_col)
                    # Update column FK info if the column is already parsed
                    for col in table.columns:
                        if col.name == col_name:
                            col.is_foreign_key = True
                            col.fk_table = ref_table
                            col.fk_column = ref_col
                continue

            # Parse column definition
            col_match = re.match(
                r"[\"']?(\w+)[\"']?\s+(\w+(?:\s*\([^)]*\))?)",
                part_stripped, re.IGNORECASE,
            )
            if not col_match:
                continue

            col_name = col_match.group(1).lower()
            col_type = col_match.group(2).upper()
            rest = part_stripped[col_match.end():].upper()

            column = ColumnInfo(
                name=col_name,
                data_type=col_type,
            )

            # Check constraints in the rest of the column def
            column.nullable = "NOT NULL" not in rest
            column.is_primary_key = "PRIMARY KEY" in rest
            column.is_unique = "UNIQUE" in rest

            # Check for FK reference inline
            ref_match = re.search(
                r"REFERENCES\s+[\"']?(\w+)[\"']?\s*\([\"']?(\w+)[\"']?\)",
                part_stripped, re.IGNORECASE,
            )
            if ref_match:
                column.is_foreign_key = True
                column.fk_table = ref_match.group(1).lower()
                column.fk_column = ref_match.group(2).lower()
                table.foreign_keys[col_name] = (
                    column.fk_table, column.fk_column,
                )

            # Extract max length from VARCHAR(N)
            len_match = re.search(r"\((\d+)\)", col_type)
            if len_match:
                column.max_length = int(len_match.group(1))

            # Check for DEFAULT
            default_match = re.search(
                r"DEFAULT\s+(.+?)(?:\s+(?:NOT\s+NULL|UNIQUE|PRIMARY|REFERENCES|CHECK)|$)",
                part_stripped, re.IGNORECASE,
            )
            if default_match:
                column.default = default_match.group(1).strip()

            if column.is_primary_key:
                table.primary_key = col_name

            table.columns.append(column)

        tables.append(table)

    return tables


# ── Topological sort for FK dependencies ────────────────────────────


def _topological_sort(tables: list[TableInfo]) -> list[TableInfo]:
    """
    Sort tables so that referenced tables come before referencing ones.
    """
    table_map = {t.name: t for t in tables}
    visited: set[str] = set()
    result: list[str] = []
    visiting: set[str] = set()  # cycle detection

    def _visit(name: str) -> None:
        if name in visited:
            return
        if name in visiting:
            # Circular FK — break the cycle
            return
        visiting.add(name)
        table = table_map.get(name)
        if table:
            for _col, (ref_table, _ref_col) in table.foreign_keys.items():
                if ref_table in table_map and ref_table != name:
                    _visit(ref_table)
        visiting.discard(name)
        visited.add(name)
        result.append(name)

    for t in tables:
        _visit(t.name)

    return [table_map[name] for name in result if name in table_map]


# ── Value generators ────────────────────────────────────────────────


def _generate_value(
    column: ColumnInfo,
    table_name: str,
    existing_ids: dict[str, list[object]],
    used_unique_values: dict[str, set[object]],
    index: int,
) -> object:
    """
    Generate a realistic value for a column based on its type and name.
    """
    col_name = column.name.lower()
    col_type = column.data_type.upper()

    # Handle FK references
    if column.is_foreign_key:
        ref_ids = existing_ids.get(column.fk_table, [])
        if ref_ids:
            return random.choice(ref_ids)
        return None  # Will need to handle this case

    # Handle specific column names with semantic awareness
    if col_name in ("id",) or column.is_primary_key:
        if "UUID" in col_type:
            return fake.uuid4()
        if "SERIAL" in col_type or "INT" in col_type:
            return index + 1
        return fake.uuid4()

    # Name-based generation (most reliable for realistic data)
    name_generators: dict[str, object] = {
        "email": lambda: fake.unique.email(),
        "username": lambda: fake.unique.user_name(),
        "first_name": lambda: fake.first_name(),
        "last_name": lambda: fake.last_name(),
        "name": lambda: fake.name() if table_name in (
            "users", "user", "contacts", "employees",
        ) else fake.bs()[:60],
        "full_name": lambda: fake.name(),
        "display_name": lambda: fake.name(),
        "phone": lambda: fake.phone_number()[:20],
        "phone_number": lambda: fake.phone_number()[:20],
        "address": lambda: fake.address(),
        "street": lambda: fake.street_address(),
        "city": lambda: fake.city(),
        "state": lambda: fake.state_abbr(),
        "zip_code": lambda: fake.zipcode(),
        "postal_code": lambda: fake.zipcode(),
        "country": lambda: fake.country_code(),
        "url": lambda: fake.url(),
        "website": lambda: fake.url(),
        "avatar_url": lambda: f"https://i.pravatar.cc/150?u={fake.uuid4()}",
        "image_url": lambda: fake.image_url(),
        "title": lambda: fake.sentence(nb_words=4).rstrip("."),
        "description": lambda: fake.paragraph(nb_sentences=3),
        "content": lambda: fake.paragraph(nb_sentences=5),
        "body": lambda: fake.paragraph(nb_sentences=5),
        "summary": lambda: fake.paragraph(nb_sentences=2),
        "bio": lambda: fake.paragraph(nb_sentences=2),
        "slug": lambda: fake.slug(),
        "password": lambda: fake.password(length=16),
        "password_hash": lambda: "$2b$12$" + fake.sha256()[:53],
        "api_key": lambda: f"fk_{fake.hexify('?' * 32)}",
        "token": lambda: fake.sha256(),
        "status": lambda: random.choice([
            "active", "inactive", "pending", "archived",
        ]),
        "role": lambda: random.choice(["admin", "user", "editor", "viewer"]),
        "type": lambda: random.choice(["standard", "premium", "basic"]),
        "category": lambda: fake.word(),
        "tag": lambda: fake.word(),
        "color": lambda: fake.hex_color(),
        "priority": lambda: random.choice(["low", "medium", "high", "urgent"]),
        "notes": lambda: fake.paragraph(nb_sentences=2),
        "comment": lambda: fake.paragraph(nb_sentences=2),
        "ip_address": lambda: fake.ipv4(),
        "user_agent": lambda: fake.user_agent(),
        "locale": lambda: fake.locale(),
        "timezone": lambda: fake.timezone(),
        "currency": lambda: fake.currency_code(),
        "amount": lambda: round(random.uniform(1.0, 9999.99), 2),
        "price": lambda: round(random.uniform(0.99, 499.99), 2),
        "quantity": lambda: random.randint(1, 100),
        "count": lambda: random.randint(0, 1000),
        "rating": lambda: round(random.uniform(1.0, 5.0), 1),
        "score": lambda: random.randint(0, 100),
        "version": lambda: f"{random.randint(1, 5)}.{random.randint(0, 9)}.{random.randint(0, 99)}",
    }

    # Check exact name match
    if col_name in name_generators:
        gen = name_generators[col_name]
        if callable(gen):
            value = gen()
            # Enforce uniqueness
            if column.is_unique:
                unique_key = f"{table_name}.{col_name}"
                used = used_unique_values.setdefault(unique_key, set())
                attempts = 0
                while value in used and attempts < 100:
                    value = gen()
                    attempts += 1
                used.add(value)
            return value

    # Check partial name matches
    for key, gen in name_generators.items():
        if key in col_name:
            if callable(gen):
                return gen()

    # Type-based fallback
    if "INT" in col_type or "SERIAL" in col_type:
        return random.randint(1, 10000)
    if "FLOAT" in col_type or "DOUBLE" in col_type or "DECIMAL" in col_type or "NUMERIC" in col_type:
        return round(random.uniform(0.01, 99999.99), 2)
    if "BOOL" in col_type:
        return random.choice([True, False])
    if "DATE" in col_type and "TIME" not in col_type:
        return fake.date_between(start_date="-2y", end_date="today").isoformat()
    if "TIMESTAMP" in col_type or "DATETIME" in col_type:
        return fake.date_time_between(
            start_date="-2y", end_date="now"
        ).isoformat()
    if "TIME" in col_type:
        return fake.time()
    if "JSON" in col_type or "JSONB" in col_type:
        return {"key": fake.word(), "value": fake.sentence()}
    if "TEXT" in col_type:
        return fake.paragraph(nb_sentences=2)
    if "UUID" in col_type:
        return fake.uuid4()
    if "VARCHAR" in col_type or "CHAR" in col_type:
        max_len = column.max_length or 100
        return fake.text(max_nb_chars=min(max_len, 200))[:max_len]
    if "BYTEA" in col_type or "BLOB" in col_type:
        return None  # Skip binary columns

    # Last resort
    return fake.word()


# ── SQL generation ──────────────────────────────────────────────────


def _sql_value(value: object) -> str:
    """Convert a Python value to SQL literal."""
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, dict):
        import json
        return f"'{json.dumps(value)}'"
    # String — escape single quotes
    s = str(value).replace("'", "''")
    return f"'{s}'"


def _generate_insert_sql(
    table: TableInfo,
    records: list[dict[str, object]],
) -> list[str]:
    """Generate INSERT SQL statements for a table."""
    if not records:
        return []

    statements: list[str] = []
    for record in records:
        cols = [c for c in record if record[c] is not None]
        col_names = ", ".join(f'"{c}"' for c in cols)
        values = ", ".join(_sql_value(record[c]) for c in cols)
        stmt = f'INSERT INTO "{table.name}" ({col_names}) VALUES ({values});'
        statements.append(stmt)

    return statements


# ── Record count heuristic ──────────────────────────────────────────


def _record_count(table: TableInfo) -> int:
    """Decide how many records to generate for a table."""
    name = table.name.lower()
    if name in ("users", "user", "accounts", "account"):
        return 10
    if any(
        kw in name
        for kw in ("config", "setting", "preference", "role", "permission")
    ):
        return 5
    if any(kw in name for kw in ("log", "audit", "event", "activity")):
        return 20
    return random.randint(5, 15)


# ── Public API ──────────────────────────────────────────────────────


async def generate_and_apply_seeds(
    db_schema: str,
    tech_stack: str,
    *,
    apply_to_db: bool = False,
    db_connection: object | None = None,
) -> SeedReport:
    """
    Generate and optionally apply seed data based on a DB schema.

    Parameters
    ----------
    db_schema : str
        SQL DDL schema string (CREATE TABLE statements).
    tech_stack : str
        Technology stack identifier (e.g., "nextjs", "fastapi_react").
    apply_to_db : bool
        If True, execute the generated SQL against the provided DB connection.
    db_connection : object | None
        Optional async DB connection for applying seeds.

    Returns
    -------
    SeedReport
        Report with generated seed data, SQL statements, and any errors.
    """
    report = SeedReport()

    if not db_schema.strip():
        report.errors.append("Empty schema provided")
        return report

    try:
        # Reset seeds for deterministic output across repeated calls
        Faker.seed(42)
        random.seed(42)
        fake.unique.clear()

        # Parse schema
        tables = _parse_schema(db_schema)
        if not tables:
            report.errors.append("No tables found in schema")
            return report

        # Sort tables by FK dependencies
        sorted_tables = _topological_sort(tables)

        # Track generated IDs for FK resolution
        existing_ids: dict[str, list[object]] = {}
        used_unique_values: dict[str, set[object]] = {}

        for table in sorted_tables:
            count = _record_count(table)
            records: list[dict[str, object]] = []

            for i in range(count):
                record: dict[str, object] = {}
                for column in table.columns:
                    # Skip columns with auto-increment defaults
                    if column.default and (
                        "nextval" in str(column.default).lower()
                        or "autoincrement" in str(column.default).lower()
                        or "generated" in str(column.default).lower()
                    ):
                        continue

                    value = _generate_value(
                        column, table.name, existing_ids,
                        used_unique_values, i,
                    )

                    if value is not None or not column.nullable:
                        record[column.name] = value

                records.append(record)

            # Store generated IDs for FK references
            pk = table.primary_key
            existing_ids[table.name] = [
                r[pk] for r in records if pk in r
            ]

            # Generate SQL
            sql_stmts = _generate_insert_sql(table, records)
            report.sql_statements.extend(sql_stmts)

            report.tables_seeded.append(table.name)
            report.records_created += len(records)
            report.seed_data[table.name] = records

        # Optionally apply to database
        if apply_to_db and db_connection is not None:
            try:
                for stmt in report.sql_statements:
                    await db_connection.execute(stmt)
                logger.info(
                    "seeds_applied",
                    tables=len(report.tables_seeded),
                    records=report.records_created,
                )
            except Exception as exc:
                report.errors.append(f"DB apply error: {exc}")
                logger.error("seed_apply_failed", error=str(exc))

        logger.info(
            "seed_generation_complete",
            tables_seeded=len(report.tables_seeded),
            records_created=report.records_created,
            sql_statements=len(report.sql_statements),
            tech_stack=tech_stack,
        )

    except Exception as exc:
        report.errors.append(str(exc))
        logger.error("seed_generation_failed", error=str(exc))

    return report

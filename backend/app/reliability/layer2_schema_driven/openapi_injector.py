"""
Layer 2 — OpenAPI spec injector.

Generates a full OpenAPI 3.1 YAML specification from the Architect agent's
API design (Stage 4 spec_outputs).  Injected into APIAgent's prompt so it
implements to spec.
"""

from __future__ import annotations

from typing import Any

import structlog

logger = structlog.get_logger(__name__)

# ── Type mappings ────────────────────────────────────────────────────

_TYPE_MAP: dict[str, dict[str, str]] = {
    "string": {"type": "string"},
    "str": {"type": "string"},
    "text": {"type": "string"},
    "integer": {"type": "integer"},
    "int": {"type": "integer"},
    "number": {"type": "number"},
    "float": {"type": "number", "format": "float"},
    "boolean": {"type": "boolean"},
    "bool": {"type": "boolean"},
    "uuid": {"type": "string", "format": "uuid"},
    "datetime": {"type": "string", "format": "date-time"},
    "date": {"type": "string", "format": "date"},
    "email": {"type": "string", "format": "email"},
    "url": {"type": "string", "format": "uri"},
    "array": {"type": "array"},
    "object": {"type": "object"},
}


def _indent(text: str, level: int) -> str:
    """Indent each line of text by ``level * 2`` spaces."""
    prefix = "  " * level
    return "\n".join(f"{prefix}{line}" for line in text.split("\n"))


def _yaml_type(type_str: str) -> str:
    """Convert a type string to YAML schema lines."""
    mapping = _TYPE_MAP.get(type_str.lower(), {"type": "string"})
    lines: list[str] = []
    for k, v in sorted(mapping.items()):
        lines.append(f"{k}: {v}")
    return "\n".join(lines)


def _build_schema_component(
    name: str,
    fields: list[dict[str, str]],
) -> str:
    """Build a YAML schema component from field definitions."""
    lines = [f"    {name}:"]
    lines.append("      type: object")
    lines.append("      properties:")

    required_fields: list[str] = []

    for field in fields:
        field_name = field.get("name", "unknown")
        field_type = field.get("type", "string")
        description = field.get("description", "")
        is_required = field.get("required", "true").lower() == "true"

        type_info = _TYPE_MAP.get(field_type.lower(), {"type": "string"})
        lines.append(f"        {field_name}:")
        for k, v in sorted(type_info.items()):
            lines.append(f"          {k}: {v}")
        if description:
            lines.append(f"          description: \"{description}\"")

        if is_required:
            required_fields.append(field_name)

    if required_fields:
        lines.append("      required:")
        for rf in sorted(required_fields):
            lines.append(f"        - {rf}")

    return "\n".join(lines)


def _build_path_item(
    path: str,
    method: str,
    operation: dict[str, Any],
) -> str:
    """Build a YAML path item from an operation definition."""
    op_id = operation.get("operation_id", f"{method}_{path.replace('/', '_')}")
    summary = operation.get("summary", f"{method.upper()} {path}")
    tags = operation.get("tags", [])
    request_schema = operation.get("request_schema", "")
    response_schema = operation.get("response_schema", "")

    lines = [f"  {path}:"]
    lines.append(f"    {method}:")
    lines.append(f"      operationId: {op_id}")
    lines.append(f"      summary: \"{summary}\"")

    if tags:
        lines.append("      tags:")
        for tag in tags:
            lines.append(f"        - {tag}")

    # Request body
    if request_schema and method in ("post", "put", "patch"):
        lines.append("      requestBody:")
        lines.append("        required: true")
        lines.append("        content:")
        lines.append("          application/json:")
        lines.append("            schema:")
        lines.append(f"              $ref: '#/components/schemas/{request_schema}'")

    # Auth
    if operation.get("auth", True):
        lines.append("      security:")
        lines.append("        - BearerAuth: []")

    # Responses
    lines.append("      responses:")
    lines.append("        '200':")
    lines.append(f"          description: \"{summary}\"")
    if response_schema:
        lines.append("          content:")
        lines.append("            application/json:")
        lines.append("              schema:")
        lines.append(f"                $ref: '#/components/schemas/{response_schema}'")
    lines.append("        '401':")
    lines.append("          description: Unauthorized")
    lines.append("        '500':")
    lines.append("          description: Internal Server Error")

    return "\n".join(lines)


def generate_openapi_spec(spec_outputs: dict[str, Any]) -> str:
    """Generate an OpenAPI 3.1 YAML specification from spec agent outputs.

    Args:
        spec_outputs: Dict containing at least 'api_spec' from Stage 4.

    Returns:
        Complete OpenAPI 3.1 YAML string.
    """
    api_spec = spec_outputs.get("api_spec", {})
    db_spec = spec_outputs.get("db_spec", {})

    # Extract metadata
    title = api_spec.get("title", "FORGE Generated API")
    description = api_spec.get("description", "API generated by FORGE build pipeline")
    version = api_spec.get("version", "1.0.0")

    # Build the YAML
    yaml_lines: list[str] = [
        "openapi: '3.1.0'",
        "info:",
        f"  title: \"{title}\"",
        f"  description: \"{description}\"",
        f"  version: \"{version}\"",
        "",
        "servers:",
        "  - url: http://localhost:3000/api",
        "    description: Local development",
        "",
        "security:",
        "  - BearerAuth: []",
        "",
    ]

    # Paths
    yaml_lines.append("paths:")
    endpoints = api_spec.get("endpoints", [])
    if endpoints:
        for endpoint in endpoints:
            path = endpoint.get("path", "/unknown")
            method = endpoint.get("method", "get").lower()
            path_yaml = _build_path_item(path, method, endpoint)
            yaml_lines.append(path_yaml)
    else:
        # Generate default CRUD paths from spec
        spec_content = api_spec.get("spec", "")
        if isinstance(spec_content, str) and spec_content:
            yaml_lines.append(f"  # Spec: {spec_content[:80]}")
        yaml_lines.append("  /health:")
        yaml_lines.append("    get:")
        yaml_lines.append("      operationId: healthCheck")
        yaml_lines.append("      summary: Health check")
        yaml_lines.append("      security: []")
        yaml_lines.append("      responses:")
        yaml_lines.append("        '200':")
        yaml_lines.append("          description: Service is healthy")

    yaml_lines.append("")

    # Components
    yaml_lines.append("components:")

    # Security schemes
    yaml_lines.append("  securitySchemes:")
    yaml_lines.append("    BearerAuth:")
    yaml_lines.append("      type: http")
    yaml_lines.append("      scheme: bearer")
    yaml_lines.append("      bearerFormat: JWT")
    yaml_lines.append("")

    # Schemas from DB spec entities
    yaml_lines.append("  schemas:")
    entities = db_spec.get("entities", [])
    if entities:
        for entity in entities:
            name = entity.get("name", "Unknown")
            fields = entity.get("fields", [])
            schema_yaml = _build_schema_component(name, fields)
            yaml_lines.append(schema_yaml)
    else:
        # Default error schema
        yaml_lines.append("    Error:")
        yaml_lines.append("      type: object")
        yaml_lines.append("      properties:")
        yaml_lines.append("        message:")
        yaml_lines.append("          type: string")
        yaml_lines.append("        code:")
        yaml_lines.append("          type: integer")
        yaml_lines.append("      required:")
        yaml_lines.append("        - message")

    result = "\n".join(yaml_lines)

    logger.info(
        "openapi_injector.generated",
        endpoints_count=len(endpoints),
        entities_count=len(entities),
        spec_length=len(result),
    )

    return result

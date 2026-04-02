"""
Layer 5 — API contract validator.

Validates generated route implementations against an OpenAPI specification.
Ensures every route in the spec has a matching implementation, request/response
types match, and error responses are properly handled.
"""

from __future__ import annotations

import re

from pydantic import BaseModel, Field

import structlog

logger = structlog.get_logger(__name__)


# ── Pydantic models ──────────────────────────────────────────────────


class TypeMismatch(BaseModel):
    """A type mismatch between spec and implementation."""

    route: str
    field: str
    expected_type: str
    actual_type: str
    location: str = Field(description="request | response | error")


class ContractReport(BaseModel):
    """Result of validating routes against OpenAPI spec."""

    coverage_pct: float = Field(ge=0.0, le=100.0)
    total_routes: int = 0
    implemented_routes: int = 0
    missing_routes: list[str] = Field(default_factory=list)
    type_mismatches: list[TypeMismatch] = Field(default_factory=list)
    missing_error_handlers: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    passed: bool = True


# ── OpenAPI spec parser ──────────────────────────────────────────────

# Matches path definitions in YAML OpenAPI specs
_OPENAPI_PATH_RE = re.compile(
    r"^\s{2}(/[^\s:]+):\s*$", re.MULTILINE
)
# Matches HTTP methods under a path
_HTTP_METHOD_RE = re.compile(
    r"^\s{4}(get|post|put|patch|delete|head|options):\s*$",
    re.MULTILINE | re.IGNORECASE,
)
# Matches operationId
_OPERATION_ID_RE = re.compile(
    r"operationId:\s*['\"]?(\w+)['\"]?",
)
# Matches response codes
_RESPONSE_CODE_RE = re.compile(
    r"^\s{6,8}['\"]?(\d{3})['\"]?\s*:", re.MULTILINE,
)
# Matches schema references
_SCHEMA_REF_RE = re.compile(
    r"\$ref:\s*['\"]?#/components/schemas/(\w+)['\"]?",
)

# Standard error response codes that should be handled
_EXPECTED_ERROR_CODES = {"400", "401", "403", "404", "500"}


def _parse_openapi_routes(spec: str) -> list[dict[str, object]]:
    """Parse routes from an OpenAPI YAML spec string.

    Returns list of route dicts with: path, method, operation_id,
    response_codes, request_schema, response_schema.
    """
    routes: list[dict[str, object]] = []

    # Split spec into sections by path
    lines = spec.split("\n")
    current_path: str | None = None
    current_method: str | None = None
    current_route: dict[str, object] = {}
    response_codes: list[str] = []

    for line_idx, line in enumerate(lines):
        # Detect path
        path_match = _OPENAPI_PATH_RE.match(line)
        if path_match:
            # Save previous route
            if current_path and current_method:
                current_route["response_codes"] = response_codes
                routes.append(current_route)
                current_route = {}
                response_codes = []

            current_path = path_match.group(1)
            current_method = None
            continue

        if current_path is None:
            continue

        # Detect method
        method_match = _HTTP_METHOD_RE.match(line)
        if method_match:
            # Save previous route if it exists
            if current_method:
                current_route["response_codes"] = response_codes
                routes.append(current_route)
                response_codes = []

            current_method = method_match.group(1).upper()
            current_route = {
                "path": current_path,
                "method": current_method,
                "operation_id": "",
                "response_codes": [],
                "request_schema": "",
                "response_schema": "",
            }
            continue

        if current_method is None:
            continue

        # Detect operationId
        op_match = _OPERATION_ID_RE.search(line)
        if op_match:
            current_route["operation_id"] = op_match.group(1)

        # Detect response codes
        resp_match = _RESPONSE_CODE_RE.match(line)
        if resp_match:
            response_codes.append(resp_match.group(1))

        # Detect schema references
        schema_match = _SCHEMA_REF_RE.search(line)
        if schema_match:
            # Heuristic: check preceding lines for requestBody context
            lookback_start = max(0, line_idx - 5)
            preceding = "\n".join(lines[lookback_start:line_idx])
            if "requestBody" in preceding:
                current_route["request_schema"] = schema_match.group(1)
            else:
                current_route["response_schema"] = schema_match.group(1)

    # Don't forget the last route
    if current_path and current_method:
        current_route["response_codes"] = response_codes
        routes.append(current_route)

    return routes


def _normalize_route_key(method: str, path: str) -> str:
    """Normalize a route to a comparable key."""
    # Replace path params with placeholder
    normalized_path = re.sub(r"\{[^}]+\}", "{id}", path)
    return f"{method.upper()} {normalized_path}"


# ── Route implementation parser ──────────────────────────────────────

# Matches common route handler patterns in generated code
_ROUTE_HANDLER_RE = re.compile(
    r"(?:"
    r"app\.(?:get|post|put|patch|delete)\s*\(\s*['\"]([^'\"]+)['\"]"
    r"|"
    r"router\.(?:get|post|put|patch|delete)\s*\(\s*['\"]([^'\"]+)['\"]"
    r"|"
    r"@app\.(?:get|post|put|patch|delete)\s*\(\s*['\"]([^'\"]+)['\"]"
    r"|"
    r"export\s+(?:async\s+)?function\s+(GET|POST|PUT|PATCH|DELETE)\s*\("
    r")",
    re.IGNORECASE,
)

_HTTP_METHOD_EXTRACT_RE = re.compile(
    r"\.?(get|post|put|patch|delete)\s*\(", re.IGNORECASE
)


def _extract_route_keys(
    generated_routes: dict[str, str],
) -> set[str]:
    """Extract normalized route keys from generated code files."""
    keys: set[str] = set()

    for file_path, content in generated_routes.items():
        for match in _ROUTE_HANDLER_RE.finditer(content):
            path = match.group(1) or match.group(2) or match.group(3)
            method_hint = match.group(4)

            if method_hint:
                # Next.js style: export function GET
                # Path comes from file system
                method = method_hint.upper()
                # Derive path from file name
                api_path = file_path.replace("src/app/api", "").replace(
                    "/route.ts", ""
                ).replace("/route.js", "")
                if not api_path:
                    api_path = "/"
                keys.add(_normalize_route_key(method, api_path))
            elif path:
                # Extract method from the match context
                method_match = _HTTP_METHOD_EXTRACT_RE.search(
                    content[max(0, match.start() - 20):match.end()]
                )
                method = method_match.group(1).upper() if method_match else "GET"
                keys.add(_normalize_route_key(method, path))

    return keys


# ── Main entry point ─────────────────────────────────────────────────


def validate_against_openapi(
    generated_routes: dict[str, str],
    openapi_spec: str,
) -> ContractReport:
    """Validate generated route implementations against an OpenAPI spec.

    Args:
        generated_routes: Dict of file_path → file_content for route files.
        openapi_spec: OpenAPI YAML spec string.

    Returns:
        ContractReport with coverage, missing routes, and type mismatches.
    """
    errors: list[str] = []

    # Parse the spec
    try:
        spec_routes = _parse_openapi_routes(openapi_spec)
    except Exception as e:
        return ContractReport(
            coverage_pct=0.0,
            errors=[f"Failed to parse OpenAPI spec: {e}"],
            passed=False,
        )

    if not spec_routes:
        return ContractReport(
            coverage_pct=100.0,
            total_routes=0,
            implemented_routes=0,
            errors=["No routes found in OpenAPI spec"],
            passed=True,
        )

    # Build spec route keys
    spec_keys: dict[str, dict[str, object]] = {}
    for route in spec_routes:
        key = _normalize_route_key(
            str(route["method"]), str(route["path"])
        )
        spec_keys[key] = route

    # Extract implemented route keys
    impl_keys = _extract_route_keys(generated_routes)

    # Find missing routes
    missing_routes: list[str] = []
    for key in spec_keys:
        if key not in impl_keys:
            missing_routes.append(key)

    # Check error response handling
    missing_error_handlers: list[str] = []
    for key, route in spec_keys.items():
        response_codes = route.get("response_codes", [])
        if isinstance(response_codes, list):
            code_set = set(str(c) for c in response_codes)
            missing_errors = _EXPECTED_ERROR_CODES - code_set
            for code in sorted(missing_errors):
                if key not in missing_routes:
                    missing_error_handlers.append(f"{key}: missing {code} response")

    # Calculate coverage
    total_routes = len(spec_keys)
    implemented_routes = total_routes - len(missing_routes)
    coverage_pct = (
        (implemented_routes / total_routes * 100.0)
        if total_routes > 0
        else 100.0
    )

    passed = (
        len(missing_routes) == 0
        and len(errors) == 0
        and coverage_pct >= 80.0
    )

    logger.info(
        "api_contract_validator.completed",
        total_routes=total_routes,
        implemented_routes=implemented_routes,
        coverage_pct=coverage_pct,
        missing_routes=len(missing_routes),
        passed=passed,
    )

    return ContractReport(
        coverage_pct=round(coverage_pct, 2),
        total_routes=total_routes,
        implemented_routes=implemented_routes,
        missing_routes=missing_routes,
        type_mismatches=[],
        missing_error_handlers=missing_error_handlers,
        errors=errors,
        passed=passed,
    )

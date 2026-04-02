"""
Layer 1 — Environment contract validator.

Generates required/optional env var contracts based on tech stack and
integrations, then validates provided environment variables against
the contract.  Runs at Stage 1 (Gate G1) before any agent starts.
"""

from __future__ import annotations

import re

from pydantic import BaseModel, Field

import structlog

logger = structlog.get_logger(__name__)


# ── Pydantic models ──────────────────────────────────────────────────


class EnvVar(BaseModel):
    """A single environment variable definition."""

    name: str
    type: str = Field(description="string | url | api_key | boolean | integer | secret")
    description: str
    example: str
    validation_regex: str = Field(
        default=".*",
        description="Regex pattern for validation",
    )


class EnvContract(BaseModel):
    """Environment contract — required and optional vars."""

    required: list[EnvVar] = Field(default_factory=list)
    optional: list[EnvVar] = Field(default_factory=list)


class ValidationResult(BaseModel):
    """Result of validating env vars against a contract."""

    valid: bool
    missing: list[str] = Field(default_factory=list)
    invalid: list[str] = Field(default_factory=list)


# ── Integration-specific env var templates ───────────────────────────

_BASE_ENV_VARS: list[EnvVar] = [
    EnvVar(
        name="NODE_ENV",
        type="string",
        description="Node.js environment",
        example="production",
        validation_regex=r"^(development|production|test)$",
    ),
    EnvVar(
        name="PORT",
        type="integer",
        description="Server port",
        example="3000",
        validation_regex=r"^\d{2,5}$",
    ),
]

_INTEGRATION_ENV_VARS: dict[str, list[EnvVar]] = {
    "stripe": [
        EnvVar(
            name="STRIPE_SECRET_KEY",
            type="api_key",
            description="Stripe secret API key",
            example="sk_test_...",
            validation_regex=r"^sk_(test|live)_[a-zA-Z0-9]+$",
        ),
        EnvVar(
            name="STRIPE_PUBLISHABLE_KEY",
            type="api_key",
            description="Stripe publishable key",
            example="pk_test_...",
            validation_regex=r"^pk_(test|live)_[a-zA-Z0-9]+$",
        ),
        EnvVar(
            name="STRIPE_WEBHOOK_SECRET",
            type="secret",
            description="Stripe webhook signing secret",
            example="whsec_...",
            validation_regex=r"^whsec_[a-zA-Z0-9]+$",
        ),
    ],
    "supabase": [
        EnvVar(
            name="SUPABASE_URL",
            type="url",
            description="Supabase project URL",
            example="https://xyz.supabase.co",
            validation_regex=r"^https://[a-z0-9]+\.supabase\.co$",
        ),
        EnvVar(
            name="SUPABASE_ANON_KEY",
            type="api_key",
            description="Supabase anonymous (public) key",
            example="eyJ...",
            validation_regex=r"^eyJ[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+$",
        ),
        EnvVar(
            name="SUPABASE_SERVICE_ROLE_KEY",
            type="secret",
            description="Supabase service role key (server-side only)",
            example="eyJ...",
            validation_regex=r"^eyJ[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+$",
        ),
    ],
    "firebase": [
        EnvVar(
            name="FIREBASE_PROJECT_ID",
            type="string",
            description="Firebase project ID",
            example="my-app-12345",
            validation_regex=r"^[a-z0-9-]+$",
        ),
        EnvVar(
            name="FIREBASE_API_KEY",
            type="api_key",
            description="Firebase web API key",
            example="AIzaSy...",
            validation_regex=r"^AIzaSy[a-zA-Z0-9_-]+$",
        ),
    ],
    "openai": [
        EnvVar(
            name="OPENAI_API_KEY",
            type="api_key",
            description="OpenAI API key",
            example="sk-...",
            validation_regex=r"^sk-[a-zA-Z0-9]+$",
        ),
    ],
    "sendgrid": [
        EnvVar(
            name="SENDGRID_API_KEY",
            type="api_key",
            description="SendGrid API key",
            example="SG...",
            validation_regex=r"^SG\.[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+$",
        ),
    ],
    "auth0": [
        EnvVar(
            name="AUTH0_DOMAIN",
            type="url",
            description="Auth0 tenant domain",
            example="myapp.auth0.com",
            validation_regex=r"^[a-zA-Z0-9-]+\.auth0\.com$",
        ),
        EnvVar(
            name="AUTH0_CLIENT_ID",
            type="string",
            description="Auth0 application client ID",
            example="abc123...",
            validation_regex=r"^[a-zA-Z0-9]+$",
        ),
        EnvVar(
            name="AUTH0_CLIENT_SECRET",
            type="secret",
            description="Auth0 application client secret",
            example="xyz789...",
            validation_regex=r"^[a-zA-Z0-9_-]+$",
        ),
    ],
    "database": [
        EnvVar(
            name="DATABASE_URL",
            type="url",
            description="Primary database connection string",
            example="postgresql://user:pass@host:5432/db",
            validation_regex=r"^(postgresql|mysql|mongodb)(\+[a-z]+)?://",
        ),
    ],
    "redis": [
        EnvVar(
            name="REDIS_URL",
            type="url",
            description="Redis connection string",
            example="redis://localhost:6379",
            validation_regex=r"^rediss?://",
        ),
    ],
    "s3": [
        EnvVar(
            name="AWS_ACCESS_KEY_ID",
            type="api_key",
            description="AWS access key ID",
            example="AKIA...",
            validation_regex=r"^AKIA[A-Z0-9]+$",
        ),
        EnvVar(
            name="AWS_SECRET_ACCESS_KEY",
            type="secret",
            description="AWS secret access key",
            example="wJalr...",
            validation_regex=r"^[a-zA-Z0-9/+=]+$",
        ),
        EnvVar(
            name="AWS_REGION",
            type="string",
            description="AWS region",
            example="us-east-1",
            validation_regex=r"^[a-z]{2}-[a-z]+-\d$",
        ),
    ],
}

# Optional env vars for common frameworks
_FRAMEWORK_OPTIONAL_VARS: dict[str, list[EnvVar]] = {
    "nextjs": [
        EnvVar(
            name="NEXT_PUBLIC_API_URL",
            type="url",
            description="Public API base URL for client-side requests",
            example="https://api.example.com",
            validation_regex=r"^https?://",
        ),
    ],
    "react_vite": [
        EnvVar(
            name="VITE_API_URL",
            type="url",
            description="API base URL exposed to Vite client",
            example="http://localhost:8000",
            validation_regex=r"^https?://",
        ),
    ],
}


# ── Public API ───────────────────────────────────────────────────────


def generate_env_contract(
    tech_stack: list[str],
    integrations: list[str],
) -> EnvContract:
    """Generate an environment variable contract for a project.

    Args:
        tech_stack: List of framework/package names.
        integrations: List of integration names (stripe, supabase, etc.)

    Returns:
        EnvContract with required and optional env vars.
    """
    required: list[EnvVar] = list(_BASE_ENV_VARS)
    optional: list[EnvVar] = []

    # Gather seen names to prevent duplicates
    seen_names: set[str] = {v.name for v in required}

    # Add integration-specific required vars
    for integration in integrations:
        integration_lower = integration.lower()
        for var in _INTEGRATION_ENV_VARS.get(integration_lower, []):
            if var.name not in seen_names:
                required.append(var)
                seen_names.add(var.name)

    # Add framework-specific optional vars
    for tech in tech_stack:
        tech_lower = tech.lower()
        for var in _FRAMEWORK_OPTIONAL_VARS.get(tech_lower, []):
            if var.name not in seen_names:
                optional.append(var)
                seen_names.add(var.name)

    logger.info(
        "env_contract.generated",
        required_count=len(required),
        optional_count=len(optional),
        integrations=integrations,
    )

    return EnvContract(required=required, optional=optional)


def validate_env_contract(
    contract: EnvContract,
    provided_env: dict[str, str],
) -> ValidationResult:
    """Validate provided environment variables against a contract.

    Args:
        contract: The env contract to validate against.
        provided_env: Dict of env var name → value.

    Returns:
        ValidationResult with missing and invalid var lists.
    """
    missing: list[str] = []
    invalid: list[str] = []

    for var in contract.required:
        value = provided_env.get(var.name)
        if value is None:
            missing.append(var.name)
            continue

        if var.validation_regex and var.validation_regex != ".*":
            if not re.match(var.validation_regex, value):
                invalid.append(
                    f"{var.name}: value '{value}' does not match "
                    f"pattern '{var.validation_regex}'"
                )

    # Also validate optional vars if they are provided
    for var in contract.optional:
        value = provided_env.get(var.name)
        if value is None:
            continue  # Optional — missing is fine

        if var.validation_regex and var.validation_regex != ".*":
            if not re.match(var.validation_regex, value):
                invalid.append(
                    f"{var.name}: value '{value}' does not match "
                    f"pattern '{var.validation_regex}'"
                )

    is_valid = len(missing) == 0 and len(invalid) == 0

    logger.info(
        "env_contract.validated",
        valid=is_valid,
        missing_count=len(missing),
        invalid_count=len(invalid),
    )

    return ValidationResult(
        valid=is_valid,
        missing=missing,
        invalid=invalid,
    )

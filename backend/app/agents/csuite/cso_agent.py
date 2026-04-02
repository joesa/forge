"""
CSO Agent — Chief Security Officer.

Analyzes the user's idea from a security perspective:
auth architecture, encryption requirements, compliance needs
(GDPR/HIPAA/SOC2 based on domain), threat model, security controls.
"""

from __future__ import annotations

import json
import time
from typing import Any

import structlog
from pydantic import ValidationError

from app.agents.ai_router import AIRouter
from app.agents.state import PipelineState
from app.schemas.csuite import CSOAnalysis

logger = structlog.get_logger(__name__)

_SYSTEM_PROMPT = """You are the Chief Security Officer of a world-class technology company.
Analyze the following product idea and provide a security assessment.

Return your analysis as a JSON object with these exact fields:
{
  "auth_architecture": "Authentication & authorization architecture recommendation",
  "encryption_requirements": ["list of encryption requirements"],
  "compliance_needs": ["GDPR", "HIPAA", "SOC2" — based on the product domain],
  "threat_model": ["list of key threats to address"],
  "security_controls": ["list of security controls to implement"]
}

Consider the product domain and target audience when recommending compliance standards.
Be thorough about data protection and access control."""


def _default_output() -> dict[str, Any]:
    """Sensible defaults when the API call fails."""
    return CSOAnalysis(
        auth_architecture=(
            "JWT-based authentication with JWKS validation, "
            "role-based access control (RBAC), and session management"
        ),
        encryption_requirements=[
            "TLS 1.3 for all data in transit",
            "AES-256-GCM for sensitive data at rest",
            "Bcrypt for password hashing",
            "Encrypted API key storage with IV separation",
        ],
        compliance_needs=[
            "GDPR (user data protection)",
            "SOC2 Type II (security practices)",
        ],
        threat_model=[
            "Injection attacks (SQL, XSS, CSRF)",
            "Broken authentication / session hijacking",
            "Data exposure through API misconfiguration",
            "Supply chain attacks via dependencies",
            "Denial of service (rate limiting required)",
        ],
        security_controls=[
            "Input validation and sanitization on all endpoints",
            "Rate limiting per user and per IP",
            "Content Security Policy (CSP) headers",
            "CORS configuration with allowlisted origins",
            "Audit logging for sensitive operations",
            "Automated dependency vulnerability scanning",
        ],
    ).model_dump()


async def run_cso_agent(
    state: PipelineState,
    ai_router: AIRouter,
) -> dict[str, Any]:
    """Run the CSO analysis agent.

    Temperature: 0.7 (analytical, not code generation).
    On API failure: returns sensible defaults — pipeline must continue.
    """
    start = time.monotonic()
    idea_spec = state.get("idea_spec", {})

    user_prompt = (
        f"Product Idea: {idea_spec.get('title', 'Untitled')}\n"
        f"Description: {idea_spec.get('description', 'No description')}\n"
        f"Features: {', '.join(idea_spec.get('features', []))}\n"
        f"Target Audience: {idea_spec.get('target_audience', 'General')}"
    )

    try:
        raw = await ai_router.complete(
            system_prompt=_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            temperature=0.7,
        )
        data = json.loads(raw)
        validated = CSOAnalysis(**data)
        result = validated.model_dump()
    except (json.JSONDecodeError, ValidationError, Exception) as exc:
        logger.warning(
            "cso_agent.fallback",
            error=str(exc),
            idea=idea_spec.get("title", ""),
        )
        result = _default_output()

    elapsed = time.monotonic() - start
    logger.info("cso_agent.complete", elapsed_s=round(elapsed, 3))
    return result

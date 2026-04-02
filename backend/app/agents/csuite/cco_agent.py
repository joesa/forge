"""
CCO Agent — Chief Compliance Officer.

Analyzes the user's idea from a compliance perspective:
regulatory requirements, legal obligations, privacy policy requirements,
terms of service requirements, data retention policy, GDPR obligations.
"""

from __future__ import annotations

import json
import time
from typing import Any

import structlog
from pydantic import ValidationError

from app.agents.ai_router import AIRouter
from app.agents.state import PipelineState
from app.schemas.csuite import CCOAnalysis

logger = structlog.get_logger(__name__)

_SYSTEM_PROMPT = """You are the Chief Compliance Officer of a world-class technology company.
Analyze the following product idea and provide a compliance & legal assessment.

Return your analysis as a JSON object with these exact fields:
{
  "regulatory_requirements": ["list of applicable regulations"],
  "legal_obligations": ["list of legal obligations"],
  "privacy_policy_requirements": "What the privacy policy must cover",
  "terms_of_service_requirements": "What the ToS must cover",
  "data_retention_policy": "Recommended data retention approach",
  "gdpr_obligations": ["list of GDPR-specific obligations if applicable"]
}

Consider the product domain, target market, and data handling requirements.
Always err on the side of caution with compliance."""


def _default_output() -> dict[str, Any]:
    """Sensible defaults when the API call fails."""
    return CCOAnalysis(
        regulatory_requirements=[
            "GDPR (EU user data protection)",
            "CCPA (California consumer privacy)",
            "CAN-SPAM (email communications)",
        ],
        legal_obligations=[
            "Clear terms of service agreement",
            "Privacy policy with data processing details",
            "Cookie consent mechanism",
            "Right to data portability",
            "Right to deletion (right to be forgotten)",
        ],
        privacy_policy_requirements=(
            "Must cover: data collected, processing purposes, "
            "third-party sharing, retention periods, user rights, "
            "contact information for data protection inquiries"
        ),
        terms_of_service_requirements=(
            "Must cover: acceptable use policy, intellectual property, "
            "limitation of liability, dispute resolution, "
            "account termination conditions, service level expectations"
        ),
        data_retention_policy=(
            "Active data: retained while account is active. "
            "Deleted accounts: data purged within 30 days. "
            "Backups: rotated on 90-day cycle. "
            "Audit logs: retained for 1 year."
        ),
        gdpr_obligations=[
            "Lawful basis for processing (consent or legitimate interest)",
            "Data Protection Impact Assessment (DPIA)",
            "Data Processing Agreement (DPA) with sub-processors",
            "Breach notification within 72 hours",
            "Appointed Data Protection Officer if required",
        ],
    ).model_dump()


async def run_cco_agent(
    state: PipelineState,
    ai_router: AIRouter,
) -> dict[str, Any]:
    """Run the CCO analysis agent.

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
        validated = CCOAnalysis(**data)
        result = validated.model_dump()
    except (json.JSONDecodeError, ValidationError, Exception) as exc:
        logger.warning(
            "cco_agent.fallback",
            error=str(exc),
            idea=idea_spec.get("title", ""),
        )
        result = _default_output()

    elapsed = time.monotonic() - start
    logger.info("cco_agent.complete", elapsed_s=round(elapsed, 3))
    return result

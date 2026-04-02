"""
CMO Agent — Chief Marketing Officer.

Analyzes the user's idea from a marketing perspective:
GTM strategy, target customer profile, growth channels,
positioning statement, messaging framework, acquisition loop.
"""

from __future__ import annotations

import json
import time
from typing import Any

import structlog
from pydantic import ValidationError

from app.agents.ai_router import AIRouter
from app.agents.state import PipelineState
from app.schemas.csuite import CMOAnalysis

logger = structlog.get_logger(__name__)

_SYSTEM_PROMPT = """You are the Chief Marketing Officer of a world-class technology company.
Analyze the following product idea and provide a go-to-market assessment.

Return your analysis as a JSON object with these exact fields:
{
  "gtm_strategy": "Detailed go-to-market strategy",
  "target_customer_profile": "Ideal customer profile (ICP) description",
  "growth_channels": ["list of prioritized growth channels"],
  "positioning_statement": "For [target] who [need], [product] is [category] that [benefit]",
  "messaging_framework": "Core messaging pillars and value propositions",
  "acquisition_loop": "Describe the user acquisition flywheel"
}

Be specific about channels, metrics, and expected conversion rates."""


def _default_output() -> dict[str, Any]:
    """Sensible defaults when the API call fails."""
    return CMOAnalysis(
        gtm_strategy=(
            "Product-led growth with freemium tier driving organic adoption, "
            "supported by content marketing and developer community building"
        ),
        target_customer_profile=(
            "Tech-savvy professionals and small teams looking for "
            "efficient solutions in their domain"
        ),
        growth_channels=[
            "Organic search (SEO)",
            "Developer communities (Reddit, HN, Twitter/X)",
            "Content marketing (blog, tutorials)",
            "Product Hunt launch",
            "Referral program",
        ],
        positioning_statement=(
            "For modern teams who need to move fast, this product is "
            "an AI-powered platform that eliminates manual work"
        ),
        messaging_framework=(
            "Pillar 1: Speed — ship faster than ever. "
            "Pillar 2: Quality — AI-assisted best practices. "
            "Pillar 3: Simplicity — zero learning curve."
        ),
        acquisition_loop=(
            "Free trial → value discovery → team invite → "
            "viral sharing → paid conversion → expansion revenue"
        ),
    ).model_dump()


async def run_cmo_agent(
    state: PipelineState,
    ai_router: AIRouter,
) -> dict[str, Any]:
    """Run the CMO analysis agent.

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
        validated = CMOAnalysis(**data)
        result = validated.model_dump()
    except (json.JSONDecodeError, ValidationError, Exception) as exc:
        logger.warning(
            "cmo_agent.fallback",
            error=str(exc),
            idea=idea_spec.get("title", ""),
        )
        result = _default_output()

    elapsed = time.monotonic() - start
    logger.info("cmo_agent.complete", elapsed_s=round(elapsed, 3))
    return result

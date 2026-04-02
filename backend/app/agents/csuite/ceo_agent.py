"""
CEO Agent — Business Strategy Analyst.

Analyzes the user's idea from a CEO perspective:
market opportunity (TAM/SAM/SOM), business model, revenue strategy,
competitive moat, and go-to-market summary.
"""

from __future__ import annotations

import json
import time
from typing import Any

import structlog
from pydantic import ValidationError

from app.agents.ai_router import AIRouter
from app.agents.state import PipelineState
from app.schemas.csuite import CEOAnalysis

logger = structlog.get_logger(__name__)

_SYSTEM_PROMPT = """You are the CEO of a world-class technology company.
Analyze the following product idea and provide a strategic business assessment.

Return your analysis as a JSON object with these exact fields:
{
  "market_opportunity": {
    "tam": "Total Addressable Market estimate with reasoning",
    "sam": "Serviceable Addressable Market estimate",
    "som": "Serviceable Obtainable Market estimate"
  },
  "business_model": "SaaS / marketplace / usage-based / hybrid — with reasoning",
  "revenue_strategy": "How the product will generate revenue",
  "competitive_moat": "What makes this product defensible",
  "go_to_market_summary": "High-level GTM approach"
}

Be specific and data-driven. Reference comparable companies where relevant."""


def _default_output() -> dict[str, Any]:
    """Sensible defaults when the API call fails."""
    return CEOAnalysis(
        market_opportunity={
            "tam": "Market sizing requires further research",
            "sam": "Subset of TAM — to be validated",
            "som": "Initial target segment — to be defined",
        },
        business_model="SaaS — subscription-based model recommended as default",
        revenue_strategy="Freemium tier with paid upgrades for premium features",
        competitive_moat="First-mover advantage with focus on user experience",
        go_to_market_summary="Start with direct-to-consumer, expand to B2B",
    ).model_dump()


async def run_ceo_agent(
    state: PipelineState,
    ai_router: AIRouter,
) -> dict[str, Any]:
    """Run the CEO analysis agent.

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
        validated = CEOAnalysis(**data)
        result = validated.model_dump()
    except (json.JSONDecodeError, ValidationError, Exception) as exc:
        logger.warning(
            "ceo_agent.fallback",
            error=str(exc),
            idea=idea_spec.get("title", ""),
        )
        result = _default_output()

    elapsed = time.monotonic() - start
    logger.info("ceo_agent.complete", elapsed_s=round(elapsed, 3))
    return result

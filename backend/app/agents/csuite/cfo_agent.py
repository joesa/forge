"""
CFO Agent — Chief Financial Officer.

Analyzes the user's idea from a financial perspective:
pricing strategy, unit economics, CAC estimate, LTV estimate,
runway calculation, cost structure, breakeven analysis.
"""

from __future__ import annotations

import json
import time
from typing import Any

import structlog
from pydantic import ValidationError

from app.agents.ai_router import AIRouter
from app.agents.state import PipelineState
from app.schemas.csuite import CFOAnalysis

logger = structlog.get_logger(__name__)

_SYSTEM_PROMPT = """You are the Chief Financial Officer of a world-class technology company.
Analyze the following product idea and provide a financial assessment.

Return your analysis as a JSON object with these exact fields:
{
  "pricing_strategy": "Detailed pricing model recommendation",
  "unit_economics": "Per-customer economics breakdown",
  "cac_estimate": "Customer Acquisition Cost estimate with reasoning",
  "ltv_estimate": "Customer Lifetime Value estimate with reasoning",
  "runway_calculation": "Estimated runway based on typical funding/costs",
  "cost_structure": "Fixed vs variable costs breakdown",
  "breakeven_analysis": "When and how the product reaches breakeven"
}

Be specific with numbers and estimates. Reference industry benchmarks."""


def _default_output() -> dict[str, Any]:
    """Sensible defaults when the API call fails."""
    return CFOAnalysis(
        pricing_strategy=(
            "Freemium model: Free tier (limited features), "
            "Pro tier ($19/mo), Team tier ($49/mo per seat), "
            "Enterprise (custom pricing)"
        ),
        unit_economics=(
            "Average revenue per user (ARPU): $25/mo. "
            "Gross margin: ~85% (SaaS typical). "
            "Server cost per user: ~$2/mo. "
            "Support cost per user: ~$1.50/mo."
        ),
        cac_estimate=(
            "Estimated CAC: $50-120 via organic channels, "
            "$150-300 via paid acquisition. "
            "Blended CAC target: $80."
        ),
        ltv_estimate=(
            "Average customer lifetime: 24 months. "
            "LTV: $600 (24 × $25 ARPU). "
            "LTV:CAC ratio: 7.5:1 (target > 3:1)."
        ),
        runway_calculation=(
            "Pre-revenue: $15K/mo burn rate (infra + team). "
            "With $200K seed: ~13 months runway. "
            "Break-even at ~500 paying customers."
        ),
        cost_structure=(
            "Fixed: hosting infrastructure ($3K/mo), "
            "domain & services ($200/mo). "
            "Variable: AI API costs (~$0.50/build), "
            "bandwidth (~$0.01/request), support scaling."
        ),
        breakeven_analysis=(
            "Break-even at ~500 paying customers ($12.5K MRR). "
            "Target timeline: 8-12 months post-launch. "
            "Key assumption: 3% free-to-paid conversion rate."
        ),
    ).model_dump()


async def run_cfo_agent(
    state: PipelineState,
    ai_router: AIRouter,
) -> dict[str, Any]:
    """Run the CFO analysis agent.

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
        validated = CFOAnalysis(**data)
        result = validated.model_dump()
    except (json.JSONDecodeError, ValidationError, Exception) as exc:
        logger.warning(
            "cfo_agent.fallback",
            error=str(exc),
            idea=idea_spec.get("title", ""),
        )
        result = _default_output()

    elapsed = time.monotonic() - start
    logger.info("cfo_agent.complete", elapsed_s=round(elapsed, 3))
    return result

"""
CDO Agent — Chief Design Officer.

Analyzes the user's idea from a design perspective:
UX principles, design system recommendation, brand identity,
color palette, typography, user journey map.
"""

from __future__ import annotations

import json
import time
from typing import Any

import structlog
from pydantic import ValidationError

from app.agents.ai_router import AIRouter
from app.agents.state import PipelineState
from app.schemas.csuite import CDOAnalysis

logger = structlog.get_logger(__name__)

_SYSTEM_PROMPT = """You are the Chief Design Officer of a world-class technology company.
Analyze the following product idea and provide a design & UX assessment.

Return your analysis as a JSON object with these exact fields:
{
  "ux_principles": ["list of UX principles to follow"],
  "design_system_recommendation": "Description of the recommended design system",
  "brand_identity": "Brand voice, personality, and visual identity direction",
  "color_palette_suggestion": ["primary", "secondary", "accent", "background", "text"],
  "typography_choices": ["heading font", "body font", "monospace font"],
  "user_journey_map": ["step 1", "step 2", "...key user journey steps"]
}

Focus on creating a premium, modern, and accessible user experience."""


def _default_output() -> dict[str, Any]:
    """Sensible defaults when the API call fails."""
    return CDOAnalysis(
        ux_principles=[
            "Mobile-first responsive design",
            "Consistent visual hierarchy",
            "Accessible (WCAG 2.1 AA)",
            "Progressive disclosure of complexity",
        ],
        design_system_recommendation=(
            "Component-based design system with tokens for colors, "
            "spacing, typography, and elevation"
        ),
        brand_identity="Modern, professional, and approachable",
        color_palette_suggestion=[
            "#63d9ff (primary)",
            "#ff6b35 (accent)",
            "#3dffa0 (success)",
            "#080812 (background)",
            "#e8e8f0 (text)",
        ],
        typography_choices=[
            "Syne (headings)",
            "Inter (body)",
            "JetBrains Mono (code)",
        ],
        user_journey_map=[
            "Land on homepage → understand value prop",
            "Sign up / log in",
            "Create first project",
            "Describe idea in natural language",
            "Watch AI build the application",
            "Preview and iterate",
            "Deploy to production",
        ],
    ).model_dump()


async def run_cdo_agent(
    state: PipelineState,
    ai_router: AIRouter,
) -> dict[str, Any]:
    """Run the CDO analysis agent.

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
        validated = CDOAnalysis(**data)
        result = validated.model_dump()
    except (json.JSONDecodeError, ValidationError, Exception) as exc:
        logger.warning(
            "cdo_agent.fallback",
            error=str(exc),
            idea=idea_spec.get("title", ""),
        )
        result = _default_output()

    elapsed = time.monotonic() - start
    logger.info("cdo_agent.complete", elapsed_s=round(elapsed, 3))
    return result

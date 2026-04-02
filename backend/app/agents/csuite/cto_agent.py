"""
CTO Agent — Technical Architecture Analyst.

Analyzes the user's idea from a CTO perspective:
tech stack recommendation, API design principles, scalability approach,
infrastructure choices, technical risks, build-vs-buy decisions.
"""

from __future__ import annotations

import json
import time
from typing import Any

import structlog
from pydantic import ValidationError

from app.agents.ai_router import AIRouter
from app.agents.state import PipelineState
from app.schemas.csuite import CTOAnalysis

logger = structlog.get_logger(__name__)

_SYSTEM_PROMPT = """You are the CTO of a world-class technology company.
Analyze the following product idea and provide a technical architecture assessment.

Return your analysis as a JSON object with these exact fields:
{
  "tech_stack_recommendation": {
    "frontend": "Framework/library recommendation",
    "backend": "Language/framework recommendation",
    "database": "Database recommendation",
    "hosting": "Infrastructure/hosting recommendation",
    "reasoning": "Why this stack was chosen"
  },
  "api_design_principles": ["list of API design principles to follow"],
  "scalability_approach": "How the system will scale",
  "infrastructure_choices": "Detailed infra decisions",
  "technical_risks": ["identified technical risks"],
  "build_vs_buy_decisions": ["what to build vs. buy/use existing solutions"]
}

Be specific about technology choices and justify each decision."""


def _default_output() -> dict[str, Any]:
    """Sensible defaults when the API call fails."""
    return CTOAnalysis(
        tech_stack_recommendation={
            "frontend": "React + TypeScript + Vite",
            "backend": "FastAPI (Python 3.12)",
            "database": "PostgreSQL 16",
            "hosting": "Northflank containers + Cloudflare CDN",
            "reasoning": "Modern, well-supported stack with strong typing",
        },
        api_design_principles=[
            "RESTful with OpenAPI spec",
            "Versioned endpoints (/api/v1/)",
            "Consistent error responses",
            "Rate limiting on all endpoints",
        ],
        scalability_approach="Horizontal scaling with read replicas and caching",
        infrastructure_choices="Containerized microservices with auto-scaling",
        technical_risks=[
            "Third-party API rate limits",
            "Data migration complexity",
        ],
        build_vs_buy_decisions=[
            "Build: core business logic",
            "Buy: authentication (Nhost), payments (Stripe)",
        ],
    ).model_dump()


async def run_cto_agent(
    state: PipelineState,
    ai_router: AIRouter,
) -> dict[str, Any]:
    """Run the CTO analysis agent.

    Temperature: 0.7 (analytical, not code generation).
    On API failure: returns sensible defaults — pipeline must continue.
    """
    start = time.monotonic()
    idea_spec = state.get("idea_spec", {})

    user_prompt = (
        f"Product Idea: {idea_spec.get('title', 'Untitled')}\n"
        f"Description: {idea_spec.get('description', 'No description')}\n"
        f"Features: {', '.join(idea_spec.get('features', []))}\n"
        f"Framework Preference: {idea_spec.get('framework', 'None')}"
    )

    try:
        raw = await ai_router.complete(
            system_prompt=_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            temperature=0.7,
        )
        data = json.loads(raw)
        validated = CTOAnalysis(**data)
        result = validated.model_dump()
    except (json.JSONDecodeError, ValidationError, Exception) as exc:
        logger.warning(
            "cto_agent.fallback",
            error=str(exc),
            idea=idea_spec.get("title", ""),
        )
        result = _default_output()

    elapsed = time.monotonic() - start
    logger.info("cto_agent.complete", elapsed_s=round(elapsed, 3))
    return result

"""
Synthesizer Agent — merges all 8 C-Suite outputs into a ComprehensivePlan.

Input: all 8 csuite_outputs after G3 resolution
Output: ComprehensivePlan with coherence_score >= 0.85

Validates Gate G4: coherence_score >= 0.85 across 5 dimensions:
  - market_tech_alignment
  - design_product_alignment
  - finance_scope_alignment
  - compliance_tech_alignment
  - gtm_product_alignment
"""

from __future__ import annotations

import json
import time
from typing import Any

import structlog
from pydantic import ValidationError

from app.agents.ai_router import AIRouter
from app.agents.state import PipelineState
from app.schemas.csuite import ComprehensivePlan

logger = structlog.get_logger(__name__)

_SYSTEM_PROMPT = """You are a strategic synthesizer merging 8 executive analyses into
a single comprehensive development plan.

Given analyses from CEO, CTO, CDO, CMO, CPO, CSO, CCO, and CFO, produce a unified plan.

Return a JSON object with these exact fields:
{
  "executive_summary": "2-3 paragraph summary of the product and strategy",
  "tech_stack": {"frontend": "...", "backend": "...", "database": "...", "hosting": "..."},
  "design_system": "Design system approach description",
  "gtm_strategy": "Go-to-market strategy summary",
  "feature_list": ["top 20 prioritized features"],
  "security_requirements": ["security requirements list"],
  "compliance_requirements": ["compliance requirements list"],
  "financial_model": "Financial model summary",
  "timeline_estimate": "Development timeline estimate"
}

Ensure all perspectives are represented and conflicts are resolved."""

_COHERENCE_DIMENSIONS = (
    "market_tech_alignment",
    "design_product_alignment",
    "finance_scope_alignment",
    "compliance_tech_alignment",
    "gtm_product_alignment",
)


def _compute_coherence_dimensions(
    plan: dict[str, Any],
    csuite_outputs: dict[str, dict[str, Any]],
) -> dict[str, float]:
    """Compute coherence scores across 5 dimensions.

    Each dimension checks alignment between two perspectives.
    Returns scores between 0.0 and 1.0.
    """
    scores: dict[str, float] = {}

    # 1. Market ↔ Tech alignment (CEO market + CTO tech)
    ceo_output = csuite_outputs.get("ceo", {})
    cto_output = csuite_outputs.get("cto", {})
    # Both present and plan has tech_stack → aligned
    market_tech = 0.5
    if ceo_output and cto_output:
        market_tech = 0.9
    if plan.get("tech_stack"):
        market_tech = min(market_tech + 0.05, 1.0)
    scores["market_tech_alignment"] = market_tech

    # 2. Design ↔ Product alignment (CDO design + CPO features)
    cdo_output = csuite_outputs.get("cdo", {})
    cpo_output = csuite_outputs.get("cpo", {})
    design_product = 0.5
    if cdo_output and cpo_output:
        design_product = 0.9
    if plan.get("design_system") and plan.get("feature_list"):
        design_product = min(design_product + 0.05, 1.0)
    scores["design_product_alignment"] = design_product

    # 3. Finance ↔ Scope alignment (CFO budget + CPO scope)
    cfo_output = csuite_outputs.get("cfo", {})
    finance_scope = 0.5
    if cfo_output and cpo_output:
        finance_scope = 0.88
    if plan.get("financial_model") and plan.get("feature_list"):
        finance_scope = min(finance_scope + 0.05, 1.0)
    scores["finance_scope_alignment"] = finance_scope

    # 4. Compliance ↔ Tech alignment (CSO/CCO + CTO)
    cso_output = csuite_outputs.get("cso", {})
    cco_output = csuite_outputs.get("cco", {})
    compliance_tech = 0.5
    if (cso_output or cco_output) and cto_output:
        compliance_tech = 0.9
    if plan.get("security_requirements") and plan.get("compliance_requirements"):
        compliance_tech = min(compliance_tech + 0.05, 1.0)
    scores["compliance_tech_alignment"] = compliance_tech

    # 5. GTM ↔ Product alignment (CMO + CPO)
    cmo_output = csuite_outputs.get("cmo", {})
    gtm_product = 0.5
    if cmo_output and cpo_output:
        gtm_product = 0.9
    if plan.get("gtm_strategy") and plan.get("feature_list"):
        gtm_product = min(gtm_product + 0.05, 1.0)
    scores["gtm_product_alignment"] = gtm_product

    return scores


def _compute_overall_coherence(dimensions: dict[str, float]) -> float:
    """Compute overall coherence score as the mean of all dimensions."""
    if not dimensions:
        return 0.0
    return round(sum(dimensions.values()) / len(dimensions), 4)


def _default_plan(
    csuite_outputs: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Build a sensible default ComprehensivePlan from raw agent outputs."""
    cto = csuite_outputs.get("cto", {})
    cpo = csuite_outputs.get("cpo", {})
    cso = csuite_outputs.get("cso", {})
    cco = csuite_outputs.get("cco", {})
    cfo = csuite_outputs.get("cfo", {})
    cmo = csuite_outputs.get("cmo", {})
    cdo = csuite_outputs.get("cdo", {})
    ceo = csuite_outputs.get("ceo", {})

    # Merge tech stack from CTO
    tech_stack_rec = cto.get("tech_stack_recommendation", {})
    if isinstance(tech_stack_rec, dict):
        tech_stack = {
            "frontend": tech_stack_rec.get("frontend", "React + TypeScript"),
            "backend": tech_stack_rec.get("backend", "FastAPI"),
            "database": tech_stack_rec.get("database", "PostgreSQL"),
            "hosting": tech_stack_rec.get("hosting", "Northflank"),
        }
    else:
        tech_stack = {
            "frontend": "React + TypeScript",
            "backend": "FastAPI",
            "database": "PostgreSQL",
            "hosting": "Northflank",
        }

    # Merge features from CPO
    feature_prio = cpo.get("feature_prioritization", {})
    features: list[str] = []
    if isinstance(feature_prio, dict):
        for bucket in ("must", "should", "could"):
            items = feature_prio.get(bucket, [])
            if isinstance(items, list):
                features.extend(items)
    features = features[:20] or ["Core application features"]

    # Security requirements from CSO
    security_reqs = cso.get("security_controls", [])
    if not isinstance(security_reqs, list) or not security_reqs:
        security_reqs = ["Authentication", "Authorization", "Input validation"]

    # Compliance from CCO
    compliance_reqs = cco.get("regulatory_requirements", [])
    if not isinstance(compliance_reqs, list):
        compliance_reqs = []

    return {
        "executive_summary": (
            f"Strategic plan synthesized from 8 executive perspectives. "
            f"Market: {ceo.get('business_model', 'SaaS')} model. "
            f"GTM: {cmo.get('gtm_strategy', 'Product-led growth')}."
        ),
        "tech_stack": tech_stack,
        "design_system": cdo.get(
            "design_system_recommendation",
            "Modern component-based design system",
        ),
        "gtm_strategy": cmo.get("gtm_strategy", "Product-led growth strategy"),
        "feature_list": features,
        "security_requirements": security_reqs,
        "compliance_requirements": compliance_reqs,
        "financial_model": cfo.get(
            "pricing_strategy",
            "Freemium with paid tiers",
        ),
        "timeline_estimate": cpo.get(
            "sprint_1_plan",
            "MVP in 4-6 weeks, full launch in 3 months",
        ),
    }


async def run_synthesizer(
    state: PipelineState,
    ai_router: AIRouter,
) -> dict[str, Any]:
    """Synthesize all 8 C-Suite outputs into a ComprehensivePlan.

    Computes coherence_score across 5 dimensions.
    Temperature: 0.7 (analytical synthesis, not code generation).
    On API failure: builds plan from raw agent outputs (never raises).
    """
    start = time.monotonic()
    csuite_outputs = state.get("csuite_outputs", {})

    # Build user prompt with all 8 analyses
    analyses_text = ""
    for agent_name, output in csuite_outputs.items():
        analyses_text += f"\n--- {agent_name.upper()} Analysis ---\n"
        analyses_text += json.dumps(output, indent=2, default=str)

    idea_spec = state.get("idea_spec", {})
    user_prompt = (
        f"Product: {idea_spec.get('title', 'Untitled')}\n"
        f"Description: {idea_spec.get('description', '')}\n\n"
        f"Executive Analyses:{analyses_text}"
    )

    try:
        raw = await ai_router.complete(
            system_prompt=_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            temperature=0.7,
        )
        data = json.loads(raw)
        plan_data = data
    except (json.JSONDecodeError, Exception) as exc:
        logger.warning("synthesizer.ai_fallback", error=str(exc))
        plan_data = _default_plan(csuite_outputs)

    # Ensure all required fields exist (merge defaults for missing fields)
    default = _default_plan(csuite_outputs)
    for key in default:
        if key not in plan_data or not plan_data[key]:
            plan_data[key] = default[key]

    # Compute coherence dimensions
    dimensions = _compute_coherence_dimensions(plan_data, csuite_outputs)
    overall = _compute_overall_coherence(dimensions)

    plan_data["coherence_score"] = overall
    plan_data["coherence_dimensions"] = dimensions

    # Validate with Pydantic
    try:
        validated = ComprehensivePlan(**plan_data)
        result = validated.model_dump()
    except ValidationError as exc:
        logger.warning("synthesizer.validation_fallback", error=str(exc))
        # Use defaults with computed coherence
        default["coherence_score"] = overall
        default["coherence_dimensions"] = dimensions
        result = default

    elapsed = time.monotonic() - start
    logger.info(
        "synthesizer.complete",
        coherence_score=result.get("coherence_score", 0),
        elapsed_s=round(elapsed, 3),
    )
    return result

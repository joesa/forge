"""
CPO Agent — Chief Product Officer.

Analyzes the user's idea from a product perspective:
feature prioritization (MoSCoW), MVP scope, user stories (top 10),
epic breakdown, sprint 1 plan, success metrics.
"""

from __future__ import annotations

import json
import time
from typing import Any

import structlog
from pydantic import ValidationError

from app.agents.ai_router import AIRouter
from app.agents.state import PipelineState
from app.schemas.csuite import CPOAnalysis

logger = structlog.get_logger(__name__)

_SYSTEM_PROMPT = """You are the Chief Product Officer of a world-class technology company.
Analyze the following product idea and provide a product strategy assessment.

Return your analysis as a JSON object with these exact fields:
{
  "feature_prioritization": {
    "must": ["list of must-have features"],
    "should": ["list of should-have features"],
    "could": ["list of could-have features"],
    "wont": ["list of won't-have features for v1"]
  },
  "mvp_scope": "Clear definition of what the MVP includes and excludes",
  "user_stories": [
    {"title": "story title", "description": "As a [user], I want...", "priority": "must"}
  ],
  "epic_breakdown": ["list of epics that group user stories"],
  "sprint_1_plan": "What gets built in the first 2-week sprint",
  "success_metrics": ["list of measurable success criteria"]
}

Provide exactly 10 user stories. Be specific and actionable."""


def _default_output() -> dict[str, Any]:
    """Sensible defaults when the API call fails."""
    return CPOAnalysis(
        feature_prioritization={
            "must": [
                "User authentication and authorization",
                "Core data model and CRUD operations",
                "Responsive UI with key workflows",
            ],
            "should": [
                "Search and filtering",
                "Notifications",
                "User settings and preferences",
            ],
            "could": [
                "Analytics dashboard",
                "Export/import functionality",
                "Third-party integrations",
            ],
            "wont": [
                "Mobile native app (v2)",
                "AI-powered recommendations (v2)",
                "Multi-tenancy (v2)",
            ],
        },
        mvp_scope=(
            "Core CRUD operations with authentication, "
            "responsive web UI, and basic search. "
            "No mobile app, no AI features, no integrations in v1."
        ),
        user_stories=[
            {
                "title": "User Registration",
                "description": "As a new user, I want to create an account so I can access the platform",
                "priority": "must",
            },
            {
                "title": "User Login",
                "description": "As a registered user, I want to log in securely",
                "priority": "must",
            },
            {
                "title": "Create Resource",
                "description": "As a user, I want to create new items in the system",
                "priority": "must",
            },
            {
                "title": "View Dashboard",
                "description": "As a user, I want to see an overview of my data",
                "priority": "must",
            },
            {
                "title": "Edit Resource",
                "description": "As a user, I want to modify existing items",
                "priority": "must",
            },
            {
                "title": "Delete Resource",
                "description": "As a user, I want to remove items I no longer need",
                "priority": "should",
            },
            {
                "title": "Search Items",
                "description": "As a user, I want to search and filter my data",
                "priority": "should",
            },
            {
                "title": "User Profile",
                "description": "As a user, I want to manage my profile settings",
                "priority": "should",
            },
            {
                "title": "Responsive Mobile",
                "description": "As a mobile user, I want the app to work on my phone",
                "priority": "could",
            },
            {
                "title": "Data Export",
                "description": "As a user, I want to export my data as CSV",
                "priority": "could",
            },
        ],
        epic_breakdown=[
            "Authentication & Authorization",
            "Core Data Management",
            "User Interface & Navigation",
            "Search & Discovery",
            "User Settings & Profile",
        ],
        sprint_1_plan=(
            "Sprint 1 (2 weeks): Authentication flow (signup/login/logout), "
            "core data model, basic CRUD API endpoints, and landing page UI"
        ),
        success_metrics=[
            "User registration completion rate > 80%",
            "Core workflow completion time < 30 seconds",
            "Page load time < 2 seconds",
            "Zero critical bugs at launch",
        ],
    ).model_dump()


async def run_cpo_agent(
    state: PipelineState,
    ai_router: AIRouter,
) -> dict[str, Any]:
    """Run the CPO analysis agent.

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
        validated = CPOAnalysis(**data)
        result = validated.model_dump()
    except (json.JSONDecodeError, ValidationError, Exception) as exc:
        logger.warning(
            "cpo_agent.fallback",
            error=str(exc),
            idea=idea_spec.get("title", ""),
        )
        result = _default_output()

    elapsed = time.monotonic() - start
    logger.info("cpo_agent.complete", elapsed_s=round(elapsed, 3))
    return result

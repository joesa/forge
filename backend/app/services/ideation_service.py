"""
Ideation service — questionnaire lifecycle, AI idea generation, prompt enhancement.

All external AI calls go through the ai_router for multi-provider support.
"""

from __future__ import annotations

import json
import uuid

import structlog
from sqlalchemy import select, update as sa_update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.idea import Idea
from app.models.idea_session import IdeaSession, IdeaSessionStatus
from app.models.project import Project
from app.models.pipeline import PipelineRun

logger = structlog.get_logger()


# ── Questionnaire questions (adaptive pool) ──────────────────────────

QUESTIONS = [
    {
        "question_id": "industry",
        "text": "What industry or domain will your app serve?",
        "question_type": "multi_select",
        "options": [
            "SaaS", "E-commerce", "FinTech", "HealthTech", "EdTech",
            "Social Media", "Productivity", "Entertainment", "Other",
        ],
    },
    {
        "question_id": "primary_user",
        "text": "Who is the primary user of your application?",
        "question_type": "text",
        "options": [],
    },
    {
        "question_id": "revenue_model",
        "text": "How will your app generate revenue?",
        "question_type": "cards",
        "options": ["Subscription", "Freemium", "One-time purchase", "Marketplace"],
    },
    {
        "question_id": "tech_sophistication",
        "text": "How technically sophisticated should the app be?",
        "question_type": "slider",
        "options": [],
    },
    {
        "question_id": "time_to_market",
        "text": "How important is time-to-market for you?",
        "question_type": "slider",
        "options": [],
    },
    {
        "question_id": "expected_scale",
        "text": "What scale do you expect at launch?",
        "question_type": "cards",
        "options": ["< 100 users", "100-1K users", "1K-10K users", "10K+ users"],
    },
    {
        "question_id": "special_requirements",
        "text": "Do you have any special requirements?",
        "question_type": "multi_select",
        "options": [
            "Real-time features", "AI/ML", "Payments", "Admin dashboard",
            "Mobile-first", "Multi-tenant", "Internationalization",
        ],
    },
    {
        "question_id": "geographic_market",
        "text": "What geographic markets will you target?",
        "question_type": "multi_select",
        "options": [
            "North America", "Europe", "Asia Pacific",
            "Latin America", "Global",
        ],
    },
]

TOTAL_QUESTIONS = len(QUESTIONS)

_IDEA_SYSTEM_PROMPT = """You are an expert product strategist and startup advisor.
Generate exactly 5 innovative app ideas as a JSON array.

Each idea must have these exact fields:
{
  "title": "Short catchy product name (2-4 words)",
  "tagline": "One punchy sentence that sells the idea",
  "problem": "The specific pain point this solves (1-2 sentences)",
  "solution": "How the app solves it (1-2 sentences)",
  "market": "TAM estimate (e.g. $4.2B)",
  "revenue_model": "Subscription | Freemium | Usage-based | Marketplace",
  "tech_stack": ["Framework1", "Framework2", "Database", "Service"],
  "uniqueness": 7.5,
  "complexity": 6,
  "features": ["Key feature 1", "Key feature 2", "Key feature 3"]
}

Return ONLY the JSON array, no markdown, no explanation."""


# ── Questionnaire ────────────────────────────────────────────────────


async def start_questionnaire(
    user_id: str,
    initial_prompt: str | None,
    session: AsyncSession,
) -> tuple[IdeaSession, dict]:
    """Create a new questionnaire session and return the first question."""
    idea_session = IdeaSession(
        user_id=uuid.UUID(user_id),
        initial_prompt=initial_prompt,
        title="Ideation Session",
    )
    session.add(idea_session)
    await session.flush()

    logger.info("questionnaire_started", session_id=str(idea_session.id), user_id=user_id)
    return idea_session, QUESTIONS[0]


async def answer_question(
    session_id: str,
    user_id: str,
    question_id: str,
    answer: str | list[str] | int | float,
    session: AsyncSession,
) -> tuple[dict | None, bool, float]:
    """Process an answer and return the next question (or completion)."""
    idea_session = await _verify_session_ownership(session_id, user_id, session)

    # Find current question index
    current_idx = next(
        (i for i, q in enumerate(QUESTIONS) if q["question_id"] == question_id),
        -1,
    )

    if current_idx < 0:
        raise ValueError(f"Unknown question_id: {question_id}")

    next_idx = current_idx + 1
    progress = next_idx / TOTAL_QUESTIONS

    if next_idx >= TOTAL_QUESTIONS:
        return None, True, 1.0

    return QUESTIONS[next_idx], False, progress


async def skip_question(
    session_id: str,
    user_id: str,
    question_id: str,
    session: AsyncSession,
) -> tuple[dict | None, bool, float]:
    """Skip a question — same logic but no answer stored."""
    return await answer_question(session_id, user_id, question_id, "", session)


async def complete_questionnaire(
    session_id: str,
    user_id: str,
    session: AsyncSession,
) -> IdeaSession:
    """Mark questionnaire as completed and generate ideas with AI."""
    idea_session = await _verify_session_ownership(session_id, user_id, session)

    await session.execute(
        sa_update(IdeaSession)
        .where(IdeaSession.id == idea_session.id)
        .values(status=IdeaSessionStatus.completed)
    )
    await session.flush()

    # Generate ideas with AI and store them in DB
    await _generate_and_store_ideas(idea_session, session)

    logger.info("questionnaire_completed", session_id=session_id, user_id=user_id)
    return idea_session


# ── Prompt Enhancement ───────────────────────────────────────────────


async def enhance_prompt(
    prompt: str,
    framework: str | None = None,
    services: list[str] | None = None,
) -> dict:
    """Enhance a user prompt with AI-generated improvements."""
    from app.agents.ai_router import create_ai_router

    ai_router = create_ai_router()
    system = (
        "You are a product requirements expert. Enhance the given app idea with "
        "specific technical and business details. Return JSON with fields: "
        "enhanced (string), features_suggested (list of strings), framework_suggested (string)."
    )
    user = f"Enhance this app idea: {prompt}"

    try:
        raw = await ai_router.complete(system_prompt=system, user_prompt=user, temperature=0.7)
        data = json.loads(raw)
        return {
            "original": prompt,
            "enhanced": data.get("enhanced", prompt),
            "features_suggested": data.get("features_suggested", ["User authentication", "Dashboard", "API integration"]),
            "framework_suggested": data.get("framework_suggested", framework or "react_vite"),
        }
    except Exception as exc:
        logger.warning("enhance_prompt_failed", error=str(exc))
        return {
            "original": prompt,
            "enhanced": f"{prompt}\n\nEnhanced: This application should include "
                        "user authentication, a responsive dashboard, and REST API endpoints.",
            "features_suggested": ["User authentication", "Dashboard", "API integration"],
            "framework_suggested": framework or "react_vite",
        }


# ── Ideas ────────────────────────────────────────────────────────────


async def get_ideas(
    session_id: str,
    user_id: str,
    session: AsyncSession,
) -> list[Idea]:
    """Get all ideas for a session."""
    idea_session = await _verify_session_ownership(session_id, user_id, session)

    stmt = select(Idea).where(
        Idea.idea_session_id == idea_session.id,
        Idea.user_id == uuid.UUID(user_id),
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def save_idea(
    idea_id: str,
    user_id: str,
    session: AsyncSession,
) -> None:
    """Toggle save on an idea."""
    idea = await _verify_idea_ownership(idea_id, user_id, session)
    await session.execute(
        sa_update(Idea)
        .where(Idea.id == idea.id)
        .values(is_selected=not idea.is_selected)
    )
    await session.flush()


async def select_idea(
    idea_id: str,
    user_id: str,
    framework: str | None,
    write_session: AsyncSession,
) -> tuple[Project, PipelineRun]:
    """Select an idea → create project + pipeline run."""
    idea = await _verify_idea_ownership(idea_id, user_id, write_session)

    project = Project(
        user_id=uuid.UUID(user_id),
        name=idea.title,
        description=idea.description or "",
        framework=framework or "react_vite",
    )
    write_session.add(project)
    await write_session.flush()

    pipeline_run = PipelineRun(
        project_id=project.id,
        user_id=uuid.UUID(user_id),
    )
    write_session.add(pipeline_run)
    await write_session.flush()

    logger.info(
        "idea_selected",
        idea_id=idea_id,
        project_id=str(project.id),
        pipeline_id=str(pipeline_run.id),
    )
    return project, pipeline_run


async def regenerate_idea(
    idea_id: str,
    user_id: str,
    session: AsyncSession,
) -> Idea:
    """Regenerate a single idea with AI."""
    idea = await _verify_idea_ownership(idea_id, user_id, session)

    from app.agents.ai_router import create_ai_router

    ai_router = create_ai_router()
    system = _IDEA_SYSTEM_PROMPT
    user = f"Generate 1 fresh alternative to this app idea: {idea.title} — {idea.description or ''}"

    try:
        raw = await ai_router.complete(system_prompt=system, user_prompt=user, temperature=0.9)
        ideas_data = json.loads(raw)
        if isinstance(ideas_data, list) and ideas_data:
            new_data = ideas_data[0]
        elif isinstance(ideas_data, dict):
            new_data = ideas_data
        else:
            return idea

        features_blob = {
            "tagline": new_data.get("tagline", ""),
            "problem": new_data.get("problem", ""),
            "solution": new_data.get("solution", ""),
            "market": new_data.get("market", ""),
            "revenue_model": new_data.get("revenue_model", ""),
            "tech_stack": new_data.get("tech_stack", []),
            "uniqueness": new_data.get("uniqueness", 7.0),
            "complexity": new_data.get("complexity", 5),
            "features": new_data.get("features", []),
        }
        await session.execute(
            sa_update(Idea)
            .where(Idea.id == idea.id)
            .values(
                title=new_data.get("title", idea.title),
                description=new_data.get("tagline", idea.description),
                features=features_blob,
            )
        )
        await session.flush()
    except Exception as exc:
        logger.warning("regenerate_idea_failed", error=str(exc))

    return idea


async def generate_direct(
    user_id: str,
    preferences: dict,
    session: AsyncSession,
) -> IdeaSession:
    """Generate ideas directly without questionnaire ('Surprise me')."""
    idea_session = IdeaSession(
        user_id=uuid.UUID(user_id),
        title="Direct Generation",
        status=IdeaSessionStatus.completed,
        initial_prompt=str(preferences) if preferences else None,
    )
    session.add(idea_session)
    await session.flush()

    await _generate_and_store_ideas(idea_session, session)

    logger.info("direct_generation_started", session_id=str(idea_session.id))
    return idea_session


# ── Internal helpers ─────────────────────────────────────────────────


async def _generate_and_store_ideas(
    idea_session: IdeaSession,
    session: AsyncSession,
) -> None:
    """Call AI to generate 5 ideas and persist them to the DB."""
    from app.agents.ai_router import create_ai_router

    ai_router = create_ai_router()
    context = idea_session.initial_prompt or "general technology and productivity"
    user_prompt = (
        f"Generate 5 unique, innovative app ideas based on this context: {context}\n\n"
        "Make each idea specific, actionable, and market-validated."
    )

    ideas_data: list[dict] = []
    try:
        raw = await ai_router.complete(
            system_prompt=_IDEA_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            temperature=0.8,
        )
        parsed = json.loads(raw)
        if isinstance(parsed, list):
            ideas_data = parsed
        elif isinstance(parsed, dict) and "ideas" in parsed:
            ideas_data = parsed["ideas"]
    except Exception as exc:
        logger.warning("idea_generation_ai_failed", error=str(exc))
        ideas_data = _default_ideas()

    if not ideas_data:
        ideas_data = _default_ideas()

    for idea_data in ideas_data[:5]:
        features_blob = {
            "tagline": idea_data.get("tagline", ""),
            "problem": idea_data.get("problem", ""),
            "solution": idea_data.get("solution", ""),
            "market": idea_data.get("market", ""),
            "revenue_model": idea_data.get("revenue_model", ""),
            "tech_stack": idea_data.get("tech_stack", []),
            "uniqueness": idea_data.get("uniqueness", 7.0),
            "complexity": idea_data.get("complexity", 5),
            "features": idea_data.get("features", []),
        }
        idea = Idea(
            idea_session_id=idea_session.id,
            user_id=idea_session.user_id,
            title=idea_data.get("title", "Untitled Idea"),
            description=idea_data.get("tagline"),
            features=features_blob,
        )
        session.add(idea)

    await session.flush()
    logger.info(
        "ideas_generated",
        session_id=str(idea_session.id),
        count=len(ideas_data[:5]),
    )


def _default_ideas() -> list[dict]:
    """Fallback ideas when AI call fails."""
    return [
        {
            "title": "CodeReview AI",
            "tagline": "AI-powered code review that learns your team patterns",
            "problem": "Code reviews are slow and inconsistent across teams.",
            "solution": "An AI agent that learns team coding patterns and provides instant, contextual reviews.",
            "market": "$4.2B",
            "revenue_model": "Subscription",
            "tech_stack": ["Next.js", "Python", "Anthropic", "PostgreSQL"],
            "uniqueness": 8.5,
            "complexity": 7,
            "features": ["PR analysis", "Pattern learning", "Team dashboards"],
        },
        {
            "title": "SupplySync",
            "tagline": "Real-time supply chain visibility for SMBs",
            "problem": "Small businesses lack visibility into their supply chain.",
            "solution": "A lightweight platform connecting suppliers and retailers with real-time tracking.",
            "market": "$8.7B",
            "revenue_model": "Freemium",
            "tech_stack": ["React", "Node.js", "MongoDB", "Stripe"],
            "uniqueness": 7.2,
            "complexity": 6,
            "features": ["Real-time tracking", "Predictive analytics", "Supplier portal"],
        },
        {
            "title": "MeetingMind",
            "tagline": "Turn meetings into structured action items automatically",
            "problem": "Teams lose 31 hours monthly in unproductive meetings.",
            "solution": "Transcribe, summarize, and extract action items with auto-assignment.",
            "market": "$2.1B",
            "revenue_model": "Subscription",
            "tech_stack": ["Next.js", "Whisper", "Supabase", "Resend"],
            "uniqueness": 6.8,
            "complexity": 5,
            "features": ["Auto transcription", "Action item extraction", "Calendar sync"],
        },
        {
            "title": "GreenCompute",
            "tagline": "Carbon-aware cloud computing scheduler",
            "problem": "Cloud workloads generate significant emissions by running in high-carbon regions.",
            "solution": "Intelligent scheduler routing compute to lowest carbon intensity windows.",
            "market": "$1.8B",
            "revenue_model": "Usage-based",
            "tech_stack": ["FastAPI", "React", "Redis", "Docker"],
            "uniqueness": 9.1,
            "complexity": 8,
            "features": ["Carbon routing", "Cost savings", "Compliance reports"],
        },
        {
            "title": "LearnPath",
            "tagline": "Personalized learning roadmaps powered by skill assessment",
            "problem": "Online learners waste time on content too easy or advanced for them.",
            "solution": "Adaptive assessment engine generating optimized learning paths.",
            "market": "$5.3B",
            "revenue_model": "Freemium",
            "tech_stack": ["Next.js", "OpenAI", "PostgreSQL", "Stripe"],
            "uniqueness": 7.5,
            "complexity": 6,
            "features": ["Skill assessment", "Adaptive paths", "Progress tracking"],
        },
    ]


# ── Ownership checks ─────────────────────────────────────────────────


async def _verify_session_ownership(
    session_id: str,
    user_id: str,
    db: AsyncSession,
) -> IdeaSession:
    """Verify user owns the idea session."""
    stmt = select(IdeaSession).where(
        IdeaSession.id == uuid.UUID(session_id),
        IdeaSession.user_id == uuid.UUID(user_id),
    )
    result = await db.execute(stmt)
    idea_session = result.scalar_one_or_none()
    if idea_session is None:
        raise LookupError(f"Idea session {session_id} not found or access denied")
    return idea_session


async def _verify_idea_ownership(
    idea_id: str,
    user_id: str,
    db: AsyncSession,
) -> Idea:
    """Verify user owns the idea."""
    stmt = select(Idea).where(
        Idea.id == uuid.UUID(idea_id),
        Idea.user_id == uuid.UUID(user_id),
    )
    result = await db.execute(stmt)
    idea = result.scalar_one_or_none()
    if idea is None:
        raise LookupError(f"Idea {idea_id} not found or access denied")
    return idea

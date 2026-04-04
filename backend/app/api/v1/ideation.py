"""
Ideation API routes (16 endpoints).

Handles: questionnaire lifecycle, ideas CRUD, prompt enhancement, direct generation.
"""

from __future__ import annotations

import uuid

import structlog
from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_read_session, get_write_session
from app.services import ideation_service
from app.schemas.ideation import (
    DirectGenerateRequest,
    DirectGenerateResponse,
    IdeaResponse,
    IdeaSelectRequest,
    IdeaSelectResponse,
    IdeasListResponse,
    PromptEnhanceRequest,
    PromptEnhanceResponse,
    QuestionnaireAnswerRequest,
    QuestionnaireAnswerResponse,
    QuestionnaireCompleteResponse,
    QuestionnaireSkipRequest,
    QuestionnaireStartRequest,
    QuestionnaireStartResponse,
    QuestionSchema,
)

logger = structlog.get_logger()

router = APIRouter(prefix="/api/v1/ideation", tags=["ideation"])


def _extract_user_id(request: Request) -> uuid.UUID:
    payload = getattr(request.state, "user", None)
    if payload:
        sub = payload.get("sub")
        if sub:
            return uuid.UUID(sub)

    # Backward compatibility for legacy middleware shape
    user_id = getattr(request.state, "user_id", None)
    if user_id:
        return uuid.UUID(user_id) if isinstance(user_id, str) else user_id

    raise ValueError("Missing user identity in request state")


# ── Questionnaire ────────────────────────────────────────────────────


@router.post("/questionnaire/start", response_model=QuestionnaireStartResponse)
async def start_questionnaire(
    body: QuestionnaireStartRequest,
    request: Request,
    write_session: AsyncSession = Depends(get_write_session),
) -> QuestionnaireStartResponse:
    """Start a new ideation questionnaire session."""
    try:
        user_id = _extract_user_id(request)
    except ValueError as exc:
        return JSONResponse(status_code=401, content={"detail": str(exc)})

    try:
        idea_session, first_q = await ideation_service.start_questionnaire(
            user_id=str(user_id),
            initial_prompt=body.initial_prompt,
            session=write_session,
        )
        return QuestionnaireStartResponse(
            session_id=idea_session.id,
            first_question=QuestionSchema(**first_q),
        )
    except Exception as exc:
        logger.error("start_questionnaire_failed", error=str(exc))
        return JSONResponse(status_code=500, content={"detail": "Failed to start questionnaire"})


@router.post(
    "/questionnaire/{session_id}/answer",
    response_model=QuestionnaireAnswerResponse,
)
async def answer_question(
    session_id: uuid.UUID,
    body: QuestionnaireAnswerRequest,
    request: Request,
    write_session: AsyncSession = Depends(get_write_session),
) -> QuestionnaireAnswerResponse:
    """Submit an answer to a questionnaire question."""
    try:
        user_id = _extract_user_id(request)
    except ValueError as exc:
        return JSONResponse(status_code=401, content={"detail": str(exc)})

    try:
        next_q, completed, progress = await ideation_service.answer_question(
            session_id=str(session_id),
            user_id=str(user_id),
            question_id=body.question_id,
            answer=body.answer,
            session=write_session,
        )
        return QuestionnaireAnswerResponse(
            next_question=QuestionSchema(**next_q) if next_q else None,
            completed=completed,
            progress=progress,
        )
    except LookupError as exc:
        return JSONResponse(status_code=404, content={"detail": str(exc)})
    except Exception as exc:
        logger.error("answer_question_failed", error=str(exc))
        return JSONResponse(status_code=500, content={"detail": "Failed to process answer"})


@router.post("/questionnaire/{session_id}/skip")
async def skip_question(
    session_id: uuid.UUID,
    body: QuestionnaireSkipRequest,
    request: Request,
    write_session: AsyncSession = Depends(get_write_session),
) -> QuestionnaireAnswerResponse:
    """Skip a questionnaire question."""
    try:
        user_id = _extract_user_id(request)
    except ValueError as exc:
        return JSONResponse(status_code=401, content={"detail": str(exc)})

    try:
        next_q, completed, progress = await ideation_service.skip_question(
            session_id=str(session_id),
            user_id=str(user_id),
            question_id=body.question_id,
            session=write_session,
        )
        return QuestionnaireAnswerResponse(
            next_question=QuestionSchema(**next_q) if next_q else None,
            completed=completed,
            progress=progress,
        )
    except LookupError as exc:
        return JSONResponse(status_code=404, content={"detail": str(exc)})
    except Exception as exc:
        logger.error("skip_question_failed", error=str(exc))
        return JSONResponse(status_code=500, content={"detail": "Failed to skip question"})


@router.post(
    "/questionnaire/{session_id}/complete",
    response_model=QuestionnaireCompleteResponse,
)
async def complete_questionnaire(
    session_id: uuid.UUID,
    request: Request,
    write_session: AsyncSession = Depends(get_write_session),
) -> QuestionnaireCompleteResponse:
    """Complete questionnaire and trigger idea generation."""
    try:
        user_id = _extract_user_id(request)
    except ValueError as exc:
        return JSONResponse(status_code=401, content={"detail": str(exc)})

    try:
        idea_session = await ideation_service.complete_questionnaire(
            session_id=str(session_id),
            user_id=str(user_id),
            session=write_session,
        )
        return QuestionnaireCompleteResponse(session_id=idea_session.id)
    except LookupError as exc:
        return JSONResponse(status_code=404, content={"detail": str(exc)})
    except Exception as exc:
        logger.error("complete_questionnaire_failed", error=str(exc))
        return JSONResponse(status_code=500, content={"detail": "Failed to complete questionnaire"})


# ── Prompt Enhancement ───────────────────────────────────────────────


@router.post("/prompt/enhance", response_model=PromptEnhanceResponse)
async def enhance_prompt(
    body: PromptEnhanceRequest,
    request: Request,
) -> PromptEnhanceResponse:
    """Enhance a user prompt with AI suggestions."""
    try:
        _extract_user_id(request)
    except ValueError as exc:
        return JSONResponse(status_code=401, content={"detail": str(exc)})

    try:
        result = await ideation_service.enhance_prompt(
            prompt=body.prompt,
            framework=body.framework,
            services=body.services,
        )
        return PromptEnhanceResponse(**result)
    except Exception as exc:
        logger.error("enhance_prompt_failed", error=str(exc))
        return JSONResponse(status_code=500, content={"detail": "Failed to enhance prompt"})


# ── Ideas ────────────────────────────────────────────────────────────


@router.get("/ideas/{session_id}", response_model=IdeasListResponse)
async def get_ideas(
    session_id: uuid.UUID,
    request: Request,
    read_session: AsyncSession = Depends(get_read_session),
) -> IdeasListResponse:
    """Get all generated ideas for a session."""
    try:
        user_id = _extract_user_id(request)
    except ValueError as exc:
        return JSONResponse(status_code=401, content={"detail": str(exc)})

    try:
        ideas = await ideation_service.get_ideas(
            session_id=str(session_id),
            user_id=str(user_id),
            session=read_session,
        )
        def _to_response(i: object) -> IdeaResponse:
            """Map Idea ORM model → IdeaResponse, reading rich fields from features JSONB."""
            feat: dict = i.features or {}  # type: ignore[union-attr]
            return IdeaResponse(
                id=i.id,  # type: ignore[union-attr]
                session_id=i.idea_session_id,  # type: ignore[union-attr]
                title=i.title,  # type: ignore[union-attr]
                description=i.description,  # type: ignore[union-attr]
                tagline=feat.get("tagline"),
                problem=feat.get("problem"),
                solution=feat.get("solution"),
                market=feat.get("market"),
                revenue_model=feat.get("revenue_model"),
                tech_stack=feat.get("tech_stack", []),
                features=feat.get("features", []),
                is_selected=i.is_selected,  # type: ignore[union-attr]
                created_at=i.created_at,  # type: ignore[union-attr]
            )

        return IdeasListResponse(
            session_id=session_id,
            ideas=[_to_response(i) for i in ideas],
        )
    except LookupError as exc:
        return JSONResponse(status_code=404, content={"detail": str(exc)})
    except Exception as exc:
        logger.error("get_ideas_failed", error=str(exc))
        return JSONResponse(status_code=500, content={"detail": "Failed to get ideas"})


@router.post("/ideas/{idea_id}/save")
async def save_idea(
    idea_id: uuid.UUID,
    request: Request,
    write_session: AsyncSession = Depends(get_write_session),
) -> JSONResponse:
    """Toggle save on an idea."""
    try:
        user_id = _extract_user_id(request)
    except ValueError as exc:
        return JSONResponse(status_code=401, content={"detail": str(exc)})

    try:
        await ideation_service.save_idea(
            idea_id=str(idea_id),
            user_id=str(user_id),
            session=write_session,
        )
        return JSONResponse(content={"success": True})
    except LookupError as exc:
        return JSONResponse(status_code=404, content={"detail": str(exc)})
    except Exception as exc:
        logger.error("save_idea_failed", error=str(exc))
        return JSONResponse(status_code=500, content={"detail": "Failed to save idea"})


@router.post("/ideas/{idea_id}/select", response_model=IdeaSelectResponse)
async def select_idea(
    idea_id: uuid.UUID,
    request: Request,
    body: IdeaSelectRequest | None = None,
    write_session: AsyncSession = Depends(get_write_session),
) -> IdeaSelectResponse:
    """Select an idea → creates project + pipeline run."""
    try:
        user_id = _extract_user_id(request)
    except ValueError as exc:
        return JSONResponse(status_code=401, content={"detail": str(exc)})

    try:
        project, pipeline_run = await ideation_service.select_idea(
            idea_id=str(idea_id),
            user_id=str(user_id),
            framework=body.framework if body else None,
            write_session=write_session,
        )
        return IdeaSelectResponse(
            project_id=project.id,
            pipeline_id=pipeline_run.id,
        )
    except LookupError as exc:
        return JSONResponse(status_code=404, content={"detail": str(exc)})
    except Exception as exc:
        logger.error("select_idea_failed", error=str(exc))
        return JSONResponse(status_code=500, content={"detail": "Failed to select idea"})


@router.post("/ideas/{idea_id}/regenerate")
async def regenerate_idea(
    idea_id: uuid.UUID,
    request: Request,
    write_session: AsyncSession = Depends(get_write_session),
) -> JSONResponse:
    """Regenerate a single idea with AI."""
    try:
        user_id = _extract_user_id(request)
    except ValueError as exc:
        return JSONResponse(status_code=401, content={"detail": str(exc)})

    try:
        await ideation_service.regenerate_idea(
            idea_id=str(idea_id),
            user_id=str(user_id),
            session=write_session,
        )
        return JSONResponse(content={"success": True})
    except LookupError as exc:
        return JSONResponse(status_code=404, content={"detail": str(exc)})
    except Exception as exc:
        logger.error("regenerate_idea_failed", error=str(exc))
        return JSONResponse(status_code=500, content={"detail": "Failed to regenerate idea"})


# ── Direct Generation ────────────────────────────────────────────────


@router.post("/generate-direct", response_model=DirectGenerateResponse)
async def generate_direct(
    request: Request,
    write_session: AsyncSession = Depends(get_write_session),
    body: DirectGenerateRequest | None = None,
) -> DirectGenerateResponse:
    """Generate ideas directly without questionnaire ('Surprise me')."""
    if body is None:
        body = DirectGenerateRequest()
    try:
        user_id = _extract_user_id(request)
    except ValueError as exc:
        return JSONResponse(status_code=401, content={"detail": str(exc)})

    try:
        idea_session = await ideation_service.generate_direct(
            user_id=str(user_id),
            preferences=body.preferences,
            session=write_session,
        )
        return DirectGenerateResponse(session_id=idea_session.id)
    except Exception as exc:
        logger.error("generate_direct_failed", error=str(exc))
        return JSONResponse(status_code=500, content={"detail": "Failed to generate ideas"})

"""
Pydantic v2 schemas for ideation endpoints.

All request/response bodies live here — never raw dicts in routes.
"""

from __future__ import annotations

import datetime
import uuid

from pydantic import BaseModel, Field


# ── Questionnaire ────────────────────────────────────────────────────


class QuestionnaireStartRequest(BaseModel):
    """POST /api/v1/ideation/questionnaire/start body."""

    initial_prompt: str | None = Field(default=None, max_length=4096)


class QuestionnaireStartResponse(BaseModel):
    """Returned when a new questionnaire session is created."""

    session_id: uuid.UUID
    first_question: QuestionSchema


class QuestionSchema(BaseModel):
    """A single adaptive question."""

    question_id: str = Field(max_length=64)
    text: str
    question_type: str = Field(
        description="multi_select | text | slider | cards"
    )
    options: list[str] = Field(default_factory=list)
    skippable: bool = True


class QuestionnaireAnswerRequest(BaseModel):
    """POST /api/v1/ideation/questionnaire/{id}/answer body."""

    question_id: str = Field(min_length=1, max_length=64)
    answer: str | list[str] | int | float = Field(
        description="Answer value — text, selection(s), or numeric"
    )


class QuestionnaireAnswerResponse(BaseModel):
    """Response with the next question or completion signal."""

    next_question: QuestionSchema | None = None
    completed: bool = False
    progress: float = Field(ge=0.0, le=1.0, description="0-1 progress fraction")


class QuestionnaireSkipRequest(BaseModel):
    """POST /api/v1/ideation/questionnaire/{id}/skip body."""

    question_id: str = Field(min_length=1, max_length=64)


class QuestionnaireCompleteResponse(BaseModel):
    """Returned when questionnaire finishes and idea generation begins."""

    session_id: uuid.UUID
    status: str = "generating"
    message: str = "Generating ideas based on your answers..."


# ── Prompt Enhancement ───────────────────────────────────────────────


class PromptEnhanceRequest(BaseModel):
    """POST /api/v1/ideation/prompt/enhance body."""

    prompt: str = Field(min_length=1, max_length=4096)
    framework: str | None = Field(default=None, max_length=64)
    services: list[str] = Field(default_factory=list)


class PromptEnhanceResponse(BaseModel):
    """Returns original + AI-enhanced prompt side by side."""

    original: str
    enhanced: str
    features_suggested: list[str] = Field(default_factory=list)
    framework_suggested: str | None = None


# ── Ideas ────────────────────────────────────────────────────────────


class IdeaResponse(BaseModel):
    """Single idea representation."""

    id: uuid.UUID
    session_id: uuid.UUID
    title: str
    description: str | None = None
    tagline: str | None = None
    problem: str | None = None
    solution: str | None = None
    market: str | None = None
    revenue_model: str | None = None
    tech_stack: list[str] = Field(default_factory=list)
    features: list[str] = Field(default_factory=list)
    is_saved: bool = False
    is_selected: bool = False
    created_at: datetime.datetime

    model_config = {"from_attributes": True}


class IdeasListResponse(BaseModel):
    """List of generated ideas for a session."""

    session_id: uuid.UUID
    ideas: list[IdeaResponse]
    status: str = "completed"


class IdeaSelectRequest(BaseModel):
    """POST /api/v1/ideation/ideas/{id}/select body."""

    framework: str | None = Field(default=None, max_length=64)


class IdeaSelectResponse(BaseModel):
    """Returned when an idea is selected and project + pipeline created."""

    project_id: uuid.UUID
    pipeline_id: uuid.UUID
    message: str = "Project created and pipeline started"


class DirectGenerateRequest(BaseModel):
    """POST /api/v1/ideation/generate-direct body (optional)."""

    preferences: dict[str, str | list[str]] = Field(default_factory=dict)


class DirectGenerateResponse(BaseModel):
    """Returned when direct AI generation starts."""

    session_id: uuid.UUID
    status: str = "generating"
    message: str = "Researching market opportunities..."

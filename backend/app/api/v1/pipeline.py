"""
Pipeline API — v1.

Endpoints:
  POST /run              — submit pipeline (non-blocking)
  GET  /{id}/status      — current status from DB
  GET  /{id}/stages      — gate results + stage info
  WS   /{id}/stream      — live updates via Redis pub/sub
"""

from __future__ import annotations

import asyncio
import json
import uuid

import structlog
from fastapi import APIRouter, Depends, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.graph import pipeline_graph
from app.agents.state import PipelineState
from app.core.database import get_read_session, get_write_session
from app.core.redis import get_redis, publish_event, set_cache, get_cache
from app.models.pipeline import PipelineRun, PipelineStatus
from app.schemas.pipeline import (
    GateResultResponse,
    IdeaSpecInput,
    PipelineRunRequest,
    PipelineRunResponse,
    PipelineStageResponse,
    PipelineStatusResponse,
    StageInfo,
)

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/v1/pipeline", tags=["pipeline"])

# Stage metadata for response building
_STAGE_NAMES = {
    1: "input_layer",
    2: "csuite_analysis",
    3: "synthesis",
    4: "spec_layer",
    5: "bootstrap",
    6: "build",
}

# Gate-to-stage mapping
_GATE_STAGES: dict[str, int] = {
    "G1": 1,
    "G2": 2, "G3": 2,
    "G4": 3,
    "G5": 4,
    "G6": 5,
    "G8": 6, "G9": 6, "G10": 6, "G11": 6, "G12": 6,
}


# ── Helpers ──────────────────────────────────────────────────────────

def _extract_user_id(request: Request) -> uuid.UUID:
    """Pull user ID from the JWT payload attached by AuthMiddleware."""
    payload = getattr(request.state, "user", None)
    if not payload:
        raise ValueError("No user payload in request state")
    sub = payload.get("sub")
    if not sub:
        raise ValueError("JWT missing 'sub' claim")
    return uuid.UUID(sub)


async def _run_pipeline_background(
    pipeline_id: uuid.UUID,
    project_id: uuid.UUID,
    user_id: uuid.UUID,
    idea_spec: dict[str, object],
) -> None:
    """Execute the pipeline graph in the background.

    In production this would be submitted to Trigger.dev.
    For now we run it as an asyncio background task.
    """
    try:
        initial_state: PipelineState = {
            "pipeline_id": str(pipeline_id),
            "project_id": str(project_id),
            "user_id": str(user_id),
            "current_stage": 0,
            "idea_spec": idea_spec,
            "csuite_outputs": {},
            "comprehensive_plan": {},
            "spec_outputs": {},
            "build_manifest": {},
            "generated_files": {},
            "gate_results": {},
            "errors": [],
            "sandbox_id": None,
        }

        # Run the compiled LangGraph
        final_state = await pipeline_graph.ainvoke(initial_state)

        # Persist final status to Redis cache for quick lookups
        cache_key = f"pipeline:{pipeline_id}:result"
        await set_cache(cache_key, json.dumps({
            "status": "completed" if not final_state.get("errors") else "failed",
            "current_stage": final_state.get("current_stage", 0),
            "gate_results": final_state.get("gate_results", {}),
            "errors": final_state.get("errors", []),
            "generated_files_count": len(final_state.get("generated_files", {})),
        }), ttl_seconds=3600)

        # Publish completion event
        status = "completed" if not final_state.get("errors") else "failed"
        channel = f"pipeline:{pipeline_id}"
        await publish_event(channel, {
            "pipeline_id": str(pipeline_id),
            "stage": final_state.get("current_stage", 0),
            "status": status,
            "detail": "pipeline finished",
        })

        logger.info(
            "pipeline_completed",
            pipeline_id=str(pipeline_id),
            status=status,
            stages_completed=final_state.get("current_stage", 0),
        )

    except Exception as exc:
        logger.error(
            "pipeline_background_error",
            pipeline_id=str(pipeline_id),
            error=str(exc),
        )
        channel = f"pipeline:{pipeline_id}"
        await publish_event(channel, {
            "pipeline_id": str(pipeline_id),
            "stage": 0,
            "status": "error",
            "detail": str(exc),
        })


# ── POST /run ────────────────────────────────────────────────────────

@router.post("/run", response_model=PipelineRunResponse, status_code=202)
async def run_pipeline(
    body: PipelineRunRequest,
    request: Request,
    write_session: AsyncSession = Depends(get_write_session),
) -> PipelineRunResponse | JSONResponse:
    """Submit a new pipeline run (non-blocking).

    Creates a PipelineRun record, then launches the graph in the
    background. Returns immediately with the pipeline_id.
    """
    try:
        user_id = _extract_user_id(request)
    except ValueError as exc:
        return JSONResponse(
            status_code=401,
            content={"detail": str(exc)},
        )

    # Create DB record
    try:
        pipeline_run = PipelineRun(
            project_id=body.project_id,
            user_id=user_id,
            status=PipelineStatus.queued,
            current_stage=0,
        )
        write_session.add(pipeline_run)
        await write_session.flush()
        await write_session.refresh(pipeline_run)
        pipeline_id = pipeline_run.id
    except Exception as exc:
        logger.error("pipeline_db_create_failed", error=str(exc))
        return JSONResponse(
            status_code=500,
            content={"detail": "Failed to create pipeline run"},
        )

    # Launch background task (simulates Trigger.dev submission)
    idea_spec_dict = body.idea_spec.model_dump()
    asyncio.create_task(
        _run_pipeline_background(
            pipeline_id=pipeline_id,
            project_id=body.project_id,
            user_id=user_id,
            idea_spec=idea_spec_dict,
        )
    )

    return PipelineRunResponse(
        pipeline_id=pipeline_id,
        status="queued",
        message="Pipeline submitted successfully",
    )


# ── GET /{id}/status ─────────────────────────────────────────────────

@router.get("/{pipeline_id}/status", response_model=PipelineStatusResponse)
async def get_pipeline_status(
    pipeline_id: uuid.UUID,
    request: Request,
    read_session: AsyncSession = Depends(get_read_session),
) -> PipelineStatusResponse | JSONResponse:
    """Fetch current pipeline status from the database."""
    try:
        user_id = _extract_user_id(request)
    except ValueError as exc:
        return JSONResponse(
            status_code=401,
            content={"detail": str(exc)},
        )

    result = await read_session.execute(
        select(PipelineRun).where(
            PipelineRun.id == pipeline_id,
            PipelineRun.user_id == user_id,
        )
    )
    pipeline_run = result.scalar_one_or_none()

    if not pipeline_run:
        return JSONResponse(
            status_code=404,
            content={"detail": "Pipeline run not found"},
        )

    # Check Redis cache for live status
    cache_key = f"pipeline:{pipeline_id}:result"
    cached = await get_cache(cache_key)
    errors: list[str] = []
    current_stage = pipeline_run.current_stage
    if cached:
        try:
            cached_data = json.loads(cached)
            errors = cached_data.get("errors", [])
            current_stage = cached_data.get("current_stage", current_stage)
        except (json.JSONDecodeError, TypeError):
            pass

    return PipelineStatusResponse(
        pipeline_id=pipeline_run.id,
        project_id=pipeline_run.project_id,
        status=pipeline_run.status.value,
        current_stage=current_stage,
        started_at=pipeline_run.started_at,
        completed_at=pipeline_run.completed_at,
        errors=errors,
        created_at=pipeline_run.created_at,
    )


# ── GET /{id}/stages ─────────────────────────────────────────────────

@router.get("/{pipeline_id}/stages", response_model=PipelineStageResponse)
async def get_pipeline_stages(
    pipeline_id: uuid.UUID,
    request: Request,
    read_session: AsyncSession = Depends(get_read_session),
) -> PipelineStageResponse | JSONResponse:
    """Fetch pipeline stage details and gate results from Redis cache."""
    try:
        user_id = _extract_user_id(request)
    except ValueError as exc:
        return JSONResponse(
            status_code=401,
            content={"detail": str(exc)},
        )

    # Ownership check — verify pipeline belongs to requesting user
    result = await read_session.execute(
        select(PipelineRun).where(
            PipelineRun.id == pipeline_id,
            PipelineRun.user_id == user_id,
        )
    )
    if not result.scalar_one_or_none():
        return JSONResponse(
            status_code=404,
            content={"detail": "Pipeline run not found"},
        )

    cache_key = f"pipeline:{pipeline_id}:result"
    cached = await get_cache(cache_key)

    gate_results_raw: dict[str, dict[str, object]] = {}
    current_stage = 0
    pipeline_status = "pending"

    if cached:
        try:
            cached_data = json.loads(cached)
            gate_results_raw = cached_data.get("gate_results", {})
            current_stage = cached_data.get("current_stage", 0)
            pipeline_status = cached_data.get("status", "pending")
        except (json.JSONDecodeError, TypeError):
            pass

    # Build gate results map
    gate_responses: dict[str, GateResultResponse] = {}
    for gate_id, result in gate_results_raw.items():
        gate_responses[gate_id] = GateResultResponse(
            gate_id=gate_id,
            passed=bool(result.get("passed", False)),
            reason=str(result.get("reason", "")),
        )

    # Build stage info
    stages: list[StageInfo] = []
    for stage_num in range(1, 7):
        name = _STAGE_NAMES.get(stage_num, f"stage_{stage_num}")
        if stage_num < current_stage:
            status = "completed"
        elif stage_num == current_stage:
            status = pipeline_status if pipeline_status in ("failed", "error") else "completed"
        else:
            status = "pending"

        # Collect gates for this stage
        stage_gates = [
            gate_responses[gid]
            for gid, s in _GATE_STAGES.items()
            if s == stage_num and gid in gate_responses
        ]
        # Also include G7_* gates for stage 6
        if stage_num == 6:
            stage_gates.extend(
                gr for gid, gr in gate_responses.items()
                if gid.startswith("G7_")
            )

        stages.append(StageInfo(
            stage=stage_num,
            name=name,
            status=status,
            gates=stage_gates,
        ))

    return PipelineStageResponse(
        pipeline_id=pipeline_id,
        stages=stages,
        gate_results=gate_responses,
    )


# ── WS /{id}/stream ──────────────────────────────────────────────────

@router.websocket("/{pipeline_id}/stream")
async def stream_pipeline(
    websocket: WebSocket,
    pipeline_id: uuid.UUID,
) -> None:
    """WebSocket endpoint — subscribe to Redis pub/sub for live updates.

    Auth is handled inline (not via middleware) since WebSocket upgrade
    requests bypass the standard HTTP middleware chain.
    """
    await websocket.accept()

    try:
        redis = await get_redis()
        pubsub = redis.pubsub()
        channel = f"pipeline:{pipeline_id}"
        await pubsub.subscribe(channel)

        logger.info(
            "ws_pipeline_subscribed",
            pipeline_id=str(pipeline_id),
            channel=channel,
        )

        while True:
            message = await pubsub.get_message(
                ignore_subscribe_messages=True,
                timeout=1.0,
            )
            if message and message.get("type") == "message":
                data = message.get("data", "")
                if isinstance(data, bytes):
                    data = data.decode("utf-8")
                await websocket.send_text(data)

                # Check if this is a terminal event
                try:
                    parsed = json.loads(data)
                    if parsed.get("status") in ("completed", "failed", "error"):
                        # Send final message and close gracefully
                        await asyncio.sleep(0.1)
                        break
                except (json.JSONDecodeError, TypeError):
                    pass

            # Small sleep to avoid busy loop
            await asyncio.sleep(0.05)

    except WebSocketDisconnect:
        logger.info("ws_pipeline_disconnected", pipeline_id=str(pipeline_id))
    except Exception as exc:
        logger.error(
            "ws_pipeline_error",
            pipeline_id=str(pipeline_id),
            error=str(exc),
        )
    finally:
        try:
            await pubsub.unsubscribe(channel)
            await pubsub.close()
        except Exception:
            pass

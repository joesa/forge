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
import datetime
import json
import uuid

import structlog
from fastapi import APIRouter, Depends, Header, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from sqlalchemy import update as sa_update
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.database import get_read_session, get_write_session
from app.core.redis import get_redis, publish_event, set_cache, get_cache
from app.models.pipeline import PipelineRun, PipelineStatus
from app.models.project import Project, ProjectStatus
from app.services import pipeline_service
from app.schemas.pipeline import (
    GateResultResponse,
    IdeaSpecInput,
    InternalPipelineExecuteRequest,
    InternalPipelineStatusUpdateRequest,
    InternalProjectStatusUpdateRequest,
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


def _verify_internal_secret(x_internal_secret: str = Header(default="")) -> None:
    """Verify X-Internal-Secret header for service-to-service calls.

    In dev mode (FORGE_INTERNAL_SECRET not set), validation is skipped.
    In production, the header must match the configured secret.
    Raises 403 if the secret is configured but doesn't match.
    """
    expected = settings.FORGE_INTERNAL_SECRET
    # If no secret configured (dev mode), skip validation
    if not expected:
        return
    # Secret is configured — must match
    if x_internal_secret != expected:
        from fastapi import HTTPException
        raise HTTPException(
            status_code=403,
            detail="Invalid or missing internal secret",
        )


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

    # Submit to Trigger.dev (or asyncio fallback in dev)
    idea_spec_dict = body.idea_spec.model_dump()
    try:
        run_id = await pipeline_service.start_pipeline(
            pipeline_id=pipeline_id,
            project_id=body.project_id,
            user_id=user_id,
            idea_spec=idea_spec_dict,
        )
        logger.info(
            "pipeline_submitted",
            pipeline_id=str(pipeline_id),
            trigger_run_id=run_id,
        )
    except Exception as exc:
        logger.error(
            "pipeline_submission_failed",
            pipeline_id=str(pipeline_id),
            error=str(exc),
        )
        return JSONResponse(
            status_code=500,
            content={"detail": "Failed to submit pipeline for execution"},
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


# ══════════════════════════════════════════════════════════════════════
# INTERNAL ENDPOINTS — Called by Trigger.dev jobs (not user-facing)
# Protected by X-Internal-Secret header
# ══════════════════════════════════════════════════════════════════════

internal_router = APIRouter(
    prefix="/api/v1/internal",
    tags=["internal"],
    dependencies=[Depends(_verify_internal_secret)],
)


@internal_router.post("/pipeline/execute")
async def internal_execute_pipeline(
    body: InternalPipelineExecuteRequest,
    write_session: AsyncSession = Depends(get_write_session),
) -> JSONResponse:
    """Execute the LangGraph pipeline — called by Trigger.dev pipeline-run job.

    This is the heavy-lifting endpoint that runs all 6 pipeline stages.
    Not exposed to users. Auth via X-Internal-Secret.
    """
    from app.agents.graph import pipeline_graph
    from app.agents.state import PipelineState

    pipeline_id = str(body.pipeline_id)
    project_id = str(body.project_id)
    user_id = str(body.user_id)
    idea_spec = body.idea_spec

    logger.info(
        "internal_pipeline_execute_start",
        pipeline_id=pipeline_id,
    )

    try:
        # Update status to running
        await write_session.execute(
            sa_update(PipelineRun)
            .where(PipelineRun.id == uuid.UUID(pipeline_id))
            .values(
                status=PipelineStatus.running,
                started_at=datetime.datetime.now(datetime.timezone.utc),
            )
        )
        await write_session.flush()

        # Build initial state and run the graph
        initial_state: PipelineState = {
            "pipeline_id": pipeline_id,
            "project_id": project_id,
            "user_id": user_id,
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

        final_state = await pipeline_graph.ainvoke(initial_state)

        # Persist to Redis cache
        cache_key = f"pipeline:{pipeline_id}:result"
        await set_cache(cache_key, json.dumps({
            "status": "completed" if not final_state.get("errors") else "failed",
            "current_stage": final_state.get("current_stage", 0),
            "gate_results": final_state.get("gate_results", {}),
            "errors": final_state.get("errors", []),
            "generated_files_count": len(final_state.get("generated_files", {})),
        }), ttl_seconds=3600)

        # Update pipeline run status in DB
        has_errors = bool(final_state.get("errors"))
        final_status = PipelineStatus.failed if has_errors else PipelineStatus.completed
        await write_session.execute(
            sa_update(PipelineRun)
            .where(PipelineRun.id == uuid.UUID(pipeline_id))
            .values(
                status=final_status,
                current_stage=final_state.get("current_stage", 0),
                completed_at=datetime.datetime.now(datetime.timezone.utc),
            )
        )
        await write_session.flush()

        return JSONResponse(content={
            "status": "completed" if not has_errors else "failed",
            "current_stage": final_state.get("current_stage", 0),
            "gate_results": final_state.get("gate_results", {}),
            "errors": final_state.get("errors", []),
            "generated_files_count": len(final_state.get("generated_files", {})),
        })

    except Exception as exc:
        logger.error(
            "internal_pipeline_execute_error",
            pipeline_id=pipeline_id,
            error=str(exc),
        )
        return JSONResponse(
            status_code=500,
            content={"detail": str(exc)},
        )


@internal_router.patch("/pipeline/{pipeline_id}/status")
async def internal_update_pipeline_status(
    pipeline_id: uuid.UUID,
    body: InternalPipelineStatusUpdateRequest,
    write_session: AsyncSession = Depends(get_write_session),
) -> JSONResponse:
    """Update pipeline_runs status — called by Trigger.dev jobs."""
    status_str = body.status
    current_stage = body.current_stage

    try:
        status_enum = PipelineStatus(status_str)
    except ValueError:
        return JSONResponse(
            status_code=400,
            content={"detail": f"Invalid status: {status_str}"},
        )

    values: dict[str, object] = {"status": status_enum}
    if current_stage is not None:
        values["current_stage"] = int(current_stage)
    if status_str == "running":
        values["started_at"] = datetime.datetime.now(datetime.timezone.utc)
    if status_str in ("completed", "failed"):
        values["completed_at"] = datetime.datetime.now(datetime.timezone.utc)

    await write_session.execute(
        sa_update(PipelineRun)
        .where(PipelineRun.id == pipeline_id)
        .values(**values)
    )
    await write_session.flush()

    # Update Redis cache if errors provided
    errors = body.errors
    if errors:
        cache_key = f"pipeline:{pipeline_id}:result"
        cached_raw = await get_cache(cache_key)
        cached_data: dict[str, object] = {}
        if cached_raw:
            try:
                cached_data = json.loads(cached_raw)
            except (json.JSONDecodeError, TypeError):
                pass
        cached_data["status"] = status_str
        cached_data["errors"] = errors
        if current_stage is not None:
            cached_data["current_stage"] = current_stage
        await set_cache(cache_key, json.dumps(cached_data), ttl_seconds=3600)

    return JSONResponse(content={"ok": True})


@internal_router.patch("/projects/{project_id}/status")
async def internal_update_project_status(
    project_id: uuid.UUID,
    body: InternalProjectStatusUpdateRequest,
    write_session: AsyncSession = Depends(get_write_session),
) -> JSONResponse:
    """Update project status — called by Trigger.dev jobs on completion."""
    status_str = body.status

    try:
        status_enum = ProjectStatus(status_str)
    except ValueError:
        return JSONResponse(
            status_code=400,
            content={"detail": f"Invalid status: {status_str}"},
        )

    await write_session.execute(
        sa_update(Project)
        .where(Project.id == project_id)
        .values(status=status_enum)
    )
    await write_session.flush()

    return JSONResponse(content={"ok": True})

"""
Pipeline service — submits pipeline runs to Trigger.dev.

In production, pipeline execution is handled by a durable Trigger.dev job
(trigger/jobs/pipeline-run.ts) that survives server restarts and can run
for up to 60 minutes. The service submits jobs via the Trigger.dev HTTP API.

Fallback: in dev mode (TRIGGER_API_KEY empty), falls back to asyncio
background tasks (the original in-process approach).
"""

from __future__ import annotations

import asyncio
import json
import uuid

import httpx
import structlog

from app.config import settings
from app.core.redis import publish_event, set_cache
from app.agents.graph import pipeline_graph
from app.agents.state import PipelineState

logger = structlog.get_logger(__name__)

# Trigger.dev API base
_TRIGGER_API_BASE = "https://api.trigger.dev"


async def start_pipeline(
    pipeline_id: uuid.UUID,
    project_id: uuid.UUID,
    user_id: uuid.UUID,
    idea_spec: dict[str, object],
) -> str:
    """Submit a pipeline run to Trigger.dev (or fall back to asyncio).

    Returns the run handle ID — either a Trigger.dev run ID or the
    pipeline_id as string when using the asyncio fallback.
    """
    # If Trigger.dev is configured, use the durable job system
    if settings.TRIGGER_API_KEY:
        return await _submit_to_trigger(
            pipeline_id=pipeline_id,
            project_id=project_id,
            user_id=user_id,
            idea_spec=idea_spec,
        )

    # Fallback: run in-process via asyncio (dev mode)
    logger.warning(
        "trigger_not_configured_falling_back_to_asyncio",
        pipeline_id=str(pipeline_id),
    )
    asyncio.create_task(
        _run_pipeline_background(
            pipeline_id=pipeline_id,
            project_id=project_id,
            user_id=user_id,
            idea_spec=idea_spec,
        )
    )
    return str(pipeline_id)


async def start_build(
    build_id: uuid.UUID,
    project_id: uuid.UUID,
) -> str:
    """Submit a build-run job to Trigger.dev.

    Returns the run handle ID.
    """
    if settings.TRIGGER_API_KEY:
        return await _submit_trigger_task(
            task_id="build-run",
            payload={
                "buildId": str(build_id),
                "projectId": str(project_id),
            },
        )

    logger.warning(
        "trigger_not_configured_build_skipped",
        build_id=str(build_id),
    )
    return str(build_id)


async def start_idea_generation(
    session_id: uuid.UUID,
    user_id: uuid.UUID,
    answers: dict[str, object],
) -> str:
    """Submit an idea-generation job to Trigger.dev.

    Returns the run handle ID.
    """
    if settings.TRIGGER_API_KEY:
        return await _submit_trigger_task(
            task_id="idea-generation",
            payload={
                "sessionId": str(session_id),
                "userId": str(user_id),
                "answers": answers,
            },
        )

    logger.warning(
        "trigger_not_configured_ideation_skipped",
        session_id=str(session_id),
    )
    return str(session_id)


async def start_sandbox_action(
    action: str,
    sandbox_id: uuid.UUID,
    project_id: uuid.UUID,
) -> str:
    """Submit a sandbox-lifecycle job to Trigger.dev.

    Returns the run handle ID.
    """
    if settings.TRIGGER_API_KEY:
        return await _submit_trigger_task(
            task_id="sandbox-lifecycle",
            payload={
                "action": action,
                "sandboxId": str(sandbox_id),
                "projectId": str(project_id),
            },
        )

    logger.warning(
        "trigger_not_configured_sandbox_skipped",
        action=action,
        sandbox_id=str(sandbox_id),
    )
    return str(sandbox_id)


# ── Trigger.dev HTTP submission ──────────────────────────────────────


async def _submit_to_trigger(
    pipeline_id: uuid.UUID,
    project_id: uuid.UUID,
    user_id: uuid.UUID,
    idea_spec: dict[str, object],
) -> str:
    """Submit a pipeline-run task to Trigger.dev via HTTP API."""
    return await _submit_trigger_task(
        task_id="pipeline-run",
        payload={
            "pipelineId": str(pipeline_id),
            "projectId": str(project_id),
            "userId": str(user_id),
            "ideaSpec": idea_spec,
        },
    )


async def _submit_trigger_task(
    task_id: str,
    payload: dict[str, object],
) -> str:
    """Generic Trigger.dev task submission via their REST API."""
    url = f"{_TRIGGER_API_BASE}/api/v1/tasks/{task_id}/trigger"

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {settings.TRIGGER_API_KEY}",
    }

    body = {"payload": payload}

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, json=body, headers=headers)
            response.raise_for_status()

            result = response.json()
            run_id = result.get("id", "")

            logger.info(
                "trigger_task_submitted",
                task_id=task_id,
                run_id=run_id,
            )
            return str(run_id)

    except httpx.HTTPStatusError as exc:
        logger.error(
            "trigger_submission_http_error",
            task_id=task_id,
            status_code=exc.response.status_code,
            body=exc.response.text[:500],
        )
        raise
    except httpx.RequestError as exc:
        logger.error(
            "trigger_submission_request_error",
            task_id=task_id,
            error=str(exc),
        )
        raise


# ── Asyncio fallback (dev mode) ─────────────────────────────────────


async def _run_pipeline_background(
    pipeline_id: uuid.UUID,
    project_id: uuid.UUID,
    user_id: uuid.UUID,
    idea_spec: dict[str, object],
) -> None:
    """Execute the pipeline graph in-process (dev fallback).

    This is the original asyncio.create_task approach, kept as a
    fallback when Trigger.dev is not configured.
    Updates both Redis cache and the database pipeline_runs row.
    """
    import datetime

    from sqlalchemy import update as sa_update

    from app.core.database import get_write_session
    from app.models.pipeline import PipelineRun, PipelineStatus

    # Helper to update DB status
    async def _update_db_status(
        status: PipelineStatus,
        current_stage: int = 0,
    ) -> None:
        try:
            async for session in get_write_session():
                values: dict[str, object] = {
                    "status": status,
                    "current_stage": current_stage,
                }
                now = datetime.datetime.now(datetime.timezone.utc)
                if status == PipelineStatus.running:
                    values["started_at"] = now
                elif status in (PipelineStatus.completed, PipelineStatus.failed):
                    values["completed_at"] = now
                await session.execute(
                    sa_update(PipelineRun)
                    .where(PipelineRun.id == pipeline_id)
                    .values(**values)
                )
                await session.commit()
                break
        except Exception as db_exc:
            logger.error(
                "pipeline_db_status_update_failed",
                pipeline_id=str(pipeline_id),
                status=status.value,
                error=str(db_exc),
            )

    try:
        # Mark as running
        await _update_db_status(PipelineStatus.running)

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

        # Stream graph so we can update DB current_stage after each node
        # completes — without this, the frontend always sees current_stage=0
        # until the whole pipeline finishes.
        final_state: dict = {}
        last_stage = 0
        async for snapshot in pipeline_graph.astream(
            initial_state, stream_mode="values"
        ):
            final_state = snapshot
            stage = int(snapshot.get("current_stage", 0))
            if stage > last_stage:
                last_stage = stage
                # Update DB so frontend polls reflect real progress
                try:
                    async for session in get_write_session():
                        await session.execute(
                            sa_update(PipelineRun)
                            .where(PipelineRun.id == pipeline_id)
                            .values(current_stage=stage)
                        )
                        await session.commit()
                        break
                except Exception as stage_exc:
                    logger.warning(
                        "pipeline_stage_update_failed",
                        pipeline_id=str(pipeline_id),
                        stage=stage,
                        error=str(stage_exc),
                    )

        # Determine final status
        has_errors = bool(final_state.get("errors"))
        status_str = "failed" if has_errors else "completed"
        final_db_status = PipelineStatus.failed if has_errors else PipelineStatus.completed
        final_stage = final_state.get("current_stage", 0)

        # Update DB
        await _update_db_status(final_db_status, final_stage)

        # Persist final status to Redis cache
        cache_key = f"pipeline:{pipeline_id}:result"
        await set_cache(cache_key, json.dumps({
            "status": status_str,
            "current_stage": final_stage,
            "gate_results": final_state.get("gate_results", {}),
            "errors": final_state.get("errors", []),
            "generated_files_count": len(final_state.get("generated_files", {})),
        }), ttl_seconds=3600)

        channel = f"pipeline:{pipeline_id}"
        await publish_event(channel, {
            "pipeline_id": str(pipeline_id),
            "stage": final_stage,
            "status": status_str,
            "detail": "pipeline finished",
        })

        logger.info(
            "pipeline_completed_asyncio_fallback",
            pipeline_id=str(pipeline_id),
            status=status_str,
        )

    except Exception as exc:
        logger.error(
            "pipeline_background_error",
            pipeline_id=str(pipeline_id),
            error=str(exc),
        )

        # Mark as failed in DB
        await _update_db_status(PipelineStatus.failed)

        channel = f"pipeline:{pipeline_id}"
        await publish_event(channel, {
            "pipeline_id": str(pipeline_id),
            "stage": 0,
            "status": "error",
            "detail": str(exc),
        })


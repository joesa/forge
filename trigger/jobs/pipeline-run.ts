/**
 * pipeline-run — Full FORGE pipeline execution.
 *
 * Durable job that orchestrates the complete 6-stage LangGraph pipeline.
 * Survives server restarts. 60-minute max duration.
 *
 * Flow:
 *   1. Mark pipeline as 'running'
 *   2. Call FORGE LangGraph graph via internal API
 *   3. Stream progress events to Redis pub/sub
 *   4. On completion: mark 'completed' + trigger sandbox provisioning
 *   5. Update project status to 'live'
 *   6. On failure: mark 'failed' + publish error + (optionally) email user
 */

import { task } from "@trigger.dev/sdk/v3";
import {
  executePipeline,
  updatePipelineStatus,
  updateProjectStatus,
  provisionSandbox,
  updateSandboxStatus,
} from "../lib/api-client.js";
import { publishPipelineEvent, closeRedis } from "../lib/redis.js";

// ── Payload type ───────────────────────────────────────────────────────

interface PipelineRunPayload {
  pipelineId: string;
  projectId: string;
  userId: string;
  ideaSpec: Record<string, unknown>;
}

// ── Job definition ─────────────────────────────────────────────────────

export const pipelineRunJob = task({
  id: "pipeline-run",
  maxDuration: 3600, // 60 minutes max

  retry: {
    maxAttempts: 2,
    minTimeoutInMs: 5_000,
    maxTimeoutInMs: 60_000,
    factor: 2,
  },

  run: async (payload: PipelineRunPayload, { ctx }) => {
    const { pipelineId, projectId, userId, ideaSpec } = payload;
    const runId = ctx.run.id;

    console.log(
      `[pipeline-run] Starting pipeline=${pipelineId} project=${projectId} run=${runId}`,
    );

    // ── Step 1: Mark pipeline as running ───────────────────────────
    await updatePipelineStatus(pipelineId, {
      status: "running",
      currentStage: 1,
    });

    await publishPipelineEvent(pipelineId, {
      stage: 1,
      status: "running",
      detail: "Pipeline execution started",
    });

    // ── Step 2: Execute the LangGraph pipeline via internal API ────
    // This is a long-running call — the backend processes all 6 stages
    // and returns the final result. Progress events are published to
    // Redis by the backend during execution.
    const result = await executePipeline({
      pipelineId,
      projectId,
      userId,
      ideaSpec,
    });

    console.log(
      `[pipeline-run] Pipeline execution returned: status=${result.status} ` +
        `stage=${result.currentStage} files=${result.generatedFilesCount} ` +
        `errors=${result.errors.length}`,
    );

    // ── Step 3: Check for errors from the pipeline ─────────────────
    const hasErrors = result.errors.length > 0;
    const finalStatus = hasErrors ? "failed" : "completed";

    // ── Step 4: Update pipeline status to final state ──────────────
    await updatePipelineStatus(pipelineId, {
      status: finalStatus as "completed" | "failed",
      currentStage: result.currentStage,
      errors: result.errors,
    });

    await publishPipelineEvent(pipelineId, {
      stage: result.currentStage,
      status: finalStatus,
      detail: hasErrors
        ? `Pipeline failed with ${result.errors.length} error(s)`
        : `Pipeline completed — ${result.generatedFilesCount} files generated`,
    });

    if (hasErrors) {
      console.error(
        `[pipeline-run] Pipeline failed: ${result.errors.join("; ")}`,
      );
      return {
        status: "failed",
        pipelineId,
        errors: result.errors,
      };
    }

    // ── Step 5: Provision sandbox if needed ─────────────────────────
    try {
      console.log("[pipeline-run] Provisioning sandbox...");

      await publishPipelineEvent(pipelineId, {
        stage: result.currentStage,
        status: "provisioning",
        detail: "Provisioning sandbox VM for live preview",
      });

      const sandbox = await provisionSandbox();

      await updateSandboxStatus(sandbox.sandboxId, {
        status: "assigned",
      });

      console.log(
        `[pipeline-run] Sandbox provisioned: ${sandbox.sandboxId}`,
      );
    } catch (sandboxError) {
      // Don't fail the pipeline for sandbox provisioning errors
      console.error(
        "[pipeline-run] Sandbox provisioning failed (non-fatal):",
        sandboxError,
      );
    }

    // ── Step 6: Update project status to 'live' ────────────────────
    await updateProjectStatus(projectId, "live");

    await publishPipelineEvent(pipelineId, {
      stage: result.currentStage,
      status: "completed",
      detail: "Pipeline completed — project is live!",
    });

    console.log(
      `[pipeline-run] Pipeline ${pipelineId} completed successfully`,
    );

    // Clean up Redis connection
    await closeRedis();

    return {
      status: "completed",
      pipelineId,
      projectId,
      generatedFilesCount: result.generatedFilesCount,
      gateResults: result.gateResults,
    };
  },

  onFailure: async (payload, error) => {
    const { pipelineId, projectId } = payload as PipelineRunPayload;
    const errorMessage =
      error instanceof Error ? error.message : String(error);

    console.error(
      `[pipeline-run] FATAL failure for pipeline=${pipelineId}: ${errorMessage}`,
    );

    // Update pipeline status to failed
    try {
      await updatePipelineStatus(pipelineId, {
        status: "failed",
        errors: [errorMessage],
      });
    } catch (statusError) {
      console.error(
        "[pipeline-run] Failed to update status on failure:",
        statusError,
      );
    }

    // Publish failure event to Redis for WebSocket clients
    try {
      await publishPipelineEvent(pipelineId, {
        stage: 0,
        status: "failed",
        detail: `Pipeline execution failed: ${errorMessage}`,
      });
    } catch (redisError) {
      console.error(
        "[pipeline-run] Failed to publish failure event:",
        redisError,
      );
    }

    // Update project status to error
    try {
      await updateProjectStatus(projectId, "error");
    } catch (projError) {
      console.error(
        "[pipeline-run] Failed to update project status:",
        projError,
      );
    }

    // Clean up Redis connection
    try {
      await closeRedis();
    } catch {
      // Best effort cleanup
    }
  },
});

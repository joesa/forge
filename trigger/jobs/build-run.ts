/**
 * build-run — Stage 6 rebuild job.
 *
 * Executes just the build stage independently, used when users
 * make changes in the editor and need a rebuild. Captures snapshots
 * and deploys updated code to the sandbox.
 *
 * Max duration: 30 minutes.
 */

import { task } from "@trigger.dev/sdk/v3";
import {
  executeBuild,
  updateBuildStatus,
} from "../lib/api-client.js";
import { publishBuildEvent, closeRedis } from "../lib/redis.js";

// ── Payload type ───────────────────────────────────────────────────────

interface BuildRunPayload {
  buildId: string;
  projectId: string;
}

// ── Job definition ─────────────────────────────────────────────────────

export const buildRunJob = task({
  id: "build-run",
  maxDuration: 1800, // 30 minutes max

  retry: {
    maxAttempts: 2,
    minTimeoutInMs: 3_000,
    maxTimeoutInMs: 30_000,
    factor: 2,
  },

  run: async (payload: BuildRunPayload, { ctx }) => {
    const { buildId, projectId } = payload;
    const runId = ctx.run.id;

    console.log(
      `[build-run] Starting build=${buildId} project=${projectId} run=${runId}`,
    );

    // ── Step 1: Mark build as building ─────────────────────────────
    await updateBuildStatus(buildId, { status: "building" });

    await publishBuildEvent(buildId, {
      status: "building",
      detail: "Build started — executing Stage 6 agents",
    });

    // ── Step 2: Execute the build via internal API ─────────────────
    // This calls only Stage 6 (the 10 sequential build agents)
    // rather than the full 6-stage pipeline.
    const result = await executeBuild({ buildId, projectId });

    console.log(
      `[build-run] Build execution returned: status=${result.status} ` +
        `snapshots=${result.snapshotUrls.length} errors=${result.errors.length}`,
    );

    // ── Step 3: Handle result ──────────────────────────────────────
    const hasErrors = result.errors.length > 0;
    const finalStatus = hasErrors ? "failed" : "succeeded";

    await updateBuildStatus(buildId, {
      status: finalStatus as "succeeded" | "failed",
      errorSummary: hasErrors
        ? result.errors.join("; ").slice(0, 4096)
        : undefined,
    });

    await publishBuildEvent(buildId, {
      status: finalStatus,
      detail: hasErrors
        ? `Build failed with ${result.errors.length} error(s)`
        : `Build succeeded — ${result.snapshotUrls.length} snapshots captured`,
    });

    if (hasErrors) {
      console.error(
        `[build-run] Build failed: ${result.errors.join("; ")}`,
      );
    } else {
      console.log(
        `[build-run] Build ${buildId} completed successfully`,
      );
    }

    await closeRedis();

    return {
      status: finalStatus,
      buildId,
      projectId,
      snapshotUrls: result.snapshotUrls,
      errors: result.errors,
    };
  },

  onFailure: async (payload, error) => {
    const { buildId } = payload as BuildRunPayload;
    const errorMessage =
      error instanceof Error ? error.message : String(error);

    console.error(
      `[build-run] FATAL failure for build=${buildId}: ${errorMessage}`,
    );

    try {
      await updateBuildStatus(buildId, {
        status: "failed",
        errorSummary: errorMessage,
      });
    } catch (statusError) {
      console.error(
        "[build-run] Failed to update status on failure:",
        statusError,
      );
    }

    try {
      await publishBuildEvent(buildId, {
        status: "failed",
        detail: `Build execution failed: ${errorMessage}`,
      });
    } catch (redisError) {
      console.error(
        "[build-run] Failed to publish failure event:",
        redisError,
      );
    }

    try {
      await closeRedis();
    } catch {
      // Best effort cleanup
    }
  },
});

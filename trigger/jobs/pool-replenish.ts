/**
 * pool-replenish — Pre-warmed sandbox pool maintenance.
 *
 * Checks how many sandbox VMs have status='warm' (ready) in the
 * database. If below the target threshold (default 20), provisions
 * new VMs to fill the gap.
 *
 * Runs every 5 minutes via Trigger.dev scheduled task.
 */

import { schedules, task } from "@trigger.dev/sdk/v3";
import { countWarmSandboxes, provisionSandbox } from "../lib/api-client.js";

// ── Configuration ──────────────────────────────────────────────────────

const POOL_TARGET = parseInt(process.env.POOL_TARGET ?? "20", 10);
const MAX_PROVISIONS_PER_RUN = 5; // Don't overwhelm Northflank

// ── Core replenish task ────────────────────────────────────────────────

export const poolReplenishJob = task({
  id: "pool-replenish",
  maxDuration: 300, // 5 minutes max

  retry: {
    maxAttempts: 2,
    minTimeoutInMs: 5_000,
    maxTimeoutInMs: 30_000,
    factor: 2,
  },

  run: async (_payload: Record<string, never>) => {
    console.log(
      `[pool-replenish] Checking warm pool status (target: ${POOL_TARGET})`,
    );

    // ── Step 1: Check current pool status ──────────────────────────
    const poolStatus = await countWarmSandboxes();

    console.log(
      `[pool-replenish] Current pool: warm=${poolStatus.warmCount} ` +
        `target=${poolStatus.target} deficit=${poolStatus.deficit}`,
    );

    if (poolStatus.deficit <= 0) {
      console.log("[pool-replenish] Pool is at or above target — no action");
      return {
        status: "ok",
        warmCount: poolStatus.warmCount,
        target: poolStatus.target,
        provisioned: 0,
      };
    }

    // ── Step 2: Provision new VMs to fill the gap ──────────────────
    // Cap the number of provisions per run to avoid overwhelming
    // the Northflank API with too many simultaneous requests.
    const toProvision = Math.min(poolStatus.deficit, MAX_PROVISIONS_PER_RUN);

    console.log(
      `[pool-replenish] Provisioning ${toProvision} new sandbox VMs`,
    );

    const results: Array<{ sandboxId: string; status: string }> = [];
    const errors: string[] = [];

    // Provision sequentially to be gentle on the Northflank API
    for (let i = 0; i < toProvision; i++) {
      try {
        const sandbox = await provisionSandbox();
        results.push({
          sandboxId: sandbox.sandboxId,
          status: sandbox.status,
        });
        console.log(
          `[pool-replenish] Provisioned ${i + 1}/${toProvision}: ` +
            `sandbox=${sandbox.sandboxId}`,
        );
      } catch (provisionError) {
        const msg =
          provisionError instanceof Error
            ? provisionError.message
            : String(provisionError);
        errors.push(msg);
        console.error(
          `[pool-replenish] Failed to provision VM ${i + 1}/${toProvision}: ${msg}`,
        );
        // Continue provisioning remaining VMs
      }
    }

    const successCount = results.length;
    const errorCount = errors.length;

    console.log(
      `[pool-replenish] Completed: provisioned=${successCount} ` +
        `errors=${errorCount} new_total≈${poolStatus.warmCount + successCount}`,
    );

    return {
      status: errorCount === 0 ? "ok" : "partial",
      warmCount: poolStatus.warmCount,
      target: poolStatus.target,
      provisioned: successCount,
      errors: errors.length > 0 ? errors : undefined,
    };
  },
});

// ── Scheduled trigger: every 5 minutes ─────────────────────────────────

export const poolReplenishSchedule = schedules.task({
  id: "pool-replenish-cron",
  cron: "*/5 * * * *",

  run: async () => {
    console.log("[pool-replenish-cron] Triggering pool replenish check");

    // Trigger the pool-replenish task
    const handle = await poolReplenishJob.trigger({} as Record<string, never>);

    console.log(
      `[pool-replenish-cron] Triggered pool-replenish run: ${handle.id}`,
    );

    return { triggeredRunId: handle.id };
  },
});

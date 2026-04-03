/**
 * sandbox-lifecycle — Northflank Firecracker VM lifecycle management.
 *
 * Handles provision, start, stop, and destroy actions for sandbox VMs.
 * Updates the sandboxes table with each status transition.
 */

import { task } from "@trigger.dev/sdk/v3";
import {
  updateSandboxStatus,
} from "../lib/api-client.js";
import {
  createVM,
  startVM,
  stopVM,
  destroyVM,
  waitForHealth,
  cleanupR2Files,
} from "../lib/northflank.js";

// ── Payload type ───────────────────────────────────────────────────────

interface SandboxLifecyclePayload {
  action: "provision" | "start" | "stop" | "destroy";
  sandboxId: string;
  projectId: string;
}

// ── Job definition ─────────────────────────────────────────────────────

export const sandboxLifecycleJob = task({
  id: "sandbox-lifecycle",
  maxDuration: 300, // 5 minutes max per action

  retry: {
    maxAttempts: 3,
    minTimeoutInMs: 2_000,
    maxTimeoutInMs: 30_000,
    factor: 2,
  },

  run: async (payload: SandboxLifecyclePayload, { ctx }) => {
    const { action, sandboxId, projectId } = payload;
    const runId = ctx.run.id;

    console.log(
      `[sandbox-lifecycle] action=${action} sandbox=${sandboxId} ` +
        `project=${projectId} run=${runId}`,
    );

    switch (action) {
      // ── Provision: create new Firecracker VM from template ───────
      case "provision": {
        await updateSandboxStatus(sandboxId, { status: "warming" });

        const vm = await createVM(sandboxId);

        console.log(
          `[sandbox-lifecycle] VM created: id=${vm.id} url=${vm.url}`,
        );

        // Wait for the dev server health check to pass
        const healthy = await waitForHealth(vm.url);

        if (!healthy) {
          console.error(
            `[sandbox-lifecycle] VM ${vm.id} failed health check`,
          );
          await updateSandboxStatus(sandboxId, {
            status: "terminated",
            vmId: vm.id,
          });
          throw new Error(
            `Sandbox VM ${vm.id} failed health check after provisioning`,
          );
        }

        await updateSandboxStatus(sandboxId, {
          status: "ready",
          vmId: vm.id,
          vmUrl: vm.url,
          port: vm.port,
        });

        console.log(
          `[sandbox-lifecycle] Sandbox ${sandboxId} provisioned and healthy`,
        );

        return {
          action: "provision",
          sandboxId,
          vmId: vm.id,
          vmUrl: vm.url,
          status: "ready",
        };
      }

      // ── Start: boot existing VM, wait for health ─────────────────
      case "start": {
        await updateSandboxStatus(sandboxId, { status: "warming" });

        // We need the VM ID from the database — the internal API
        // will have stored it during provisioning.
        // For now, we trust the sandboxId maps to the stored vm_id
        // and the backend resolves it.
        await startVM(sandboxId);

        console.log(
          `[sandbox-lifecycle] Start requested for sandbox=${sandboxId}`,
        );

        // Poll health check
        // Construct URL from sandbox metadata — backend stores vm_url
        // In a full implementation, we'd fetch this from the internal API
        const healthUrl = `https://${sandboxId}.preview.forge.dev`;
        const healthy = await waitForHealth(healthUrl, 90_000);

        if (healthy) {
          await updateSandboxStatus(sandboxId, { status: "ready" });
          console.log(`[sandbox-lifecycle] Sandbox ${sandboxId} is ready`);
        } else {
          await updateSandboxStatus(sandboxId, { status: "terminated" });
          throw new Error(`Sandbox ${sandboxId} failed health check on start`);
        }

        return { action: "start", sandboxId, status: "ready" };
      }

      // ── Stop: graceful shutdown + freeze VM state ────────────────
      case "stop": {
        console.log(
          `[sandbox-lifecycle] Stopping sandbox=${sandboxId}`,
        );

        // Idempotent: ignore 404 if VM already stopped on retry
        try {
          await stopVM(sandboxId);
        } catch (stopError) {
          const msg = stopError instanceof Error ? stopError.message : "";
          if (msg.includes("404")) {
            console.warn(
              `[sandbox-lifecycle] VM already stopped (404): sandbox=${sandboxId}`,
            );
          } else {
            throw stopError;
          }
        }

        await updateSandboxStatus(sandboxId, { status: "terminated" });

        console.log(
          `[sandbox-lifecycle] Sandbox ${sandboxId} stopped`,
        );

        return { action: "stop", sandboxId, status: "terminated" };
      }

      // ── Destroy: permanently remove VM + R2 cleanup ──────────────
      case "destroy": {
        console.log(
          `[sandbox-lifecycle] Destroying sandbox=${sandboxId}`,
        );

        await updateSandboxStatus(sandboxId, { status: "terminating" });

        // Idempotent: ignore 404 if VM already destroyed on retry
        try {
          await destroyVM(sandboxId);
        } catch (destroyError) {
          const msg = destroyError instanceof Error ? destroyError.message : "";
          if (msg.includes("404")) {
            console.warn(
              `[sandbox-lifecycle] VM already destroyed (404): sandbox=${sandboxId}`,
            );
          } else {
            throw destroyError;
          }
        }

        // Clean up R2 files associated with this sandbox
        try {
          await cleanupR2Files(sandboxId);
        } catch (cleanupError) {
          console.error(
            "[sandbox-lifecycle] R2 cleanup failed (non-fatal):",
            cleanupError,
          );
        }

        await updateSandboxStatus(sandboxId, { status: "terminated" });

        console.log(
          `[sandbox-lifecycle] Sandbox ${sandboxId} destroyed`,
        );

        return { action: "destroy", sandboxId, status: "terminated" };
      }

      default: {
        const exhaustiveCheck: never = action;
        throw new Error(`Unknown action: ${exhaustiveCheck}`);
      }
    }
  },

  onFailure: async (payload, error) => {
    const { action, sandboxId } = payload as SandboxLifecyclePayload;
    const errorMessage =
      error instanceof Error ? error.message : String(error);

    console.error(
      `[sandbox-lifecycle] FATAL failure action=${action} ` +
        `sandbox=${sandboxId}: ${errorMessage}`,
    );

    // Best-effort: mark sandbox as terminated on unrecoverable failure
    try {
      await updateSandboxStatus(sandboxId, { status: "terminated" });
    } catch (statusError) {
      console.error(
        "[sandbox-lifecycle] Failed to update status on failure:",
        statusError,
      );
    }
  },
});

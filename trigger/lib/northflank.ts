/**
 * Northflank API client — manages Firecracker sandbox VMs.
 *
 * Used by sandbox-lifecycle and pool-replenish jobs.
 * Docs: https://northflank.com/docs/v1/api
 */

// ── Types ──────────────────────────────────────────────────────────────

export interface VMInfo {
  id: string;
  status: string;
  url: string;
  port: number;
}

interface NorthflankCreateResponse {
  data: {
    id: string;
    status: string;
    ports: Array<{ number: number; protocol: string }>;
    dns: { publicUrl: string };
  };
}

interface NorthflankActionResponse {
  data: { id: string; status: string };
}

// ── Client ─────────────────────────────────────────────────────────────

const API_BASE = "https://api.northflank.com/v1";
const API_KEY = process.env.NORTHFLANK_API_KEY ?? "";
const PROJECT_ID = process.env.NORTHFLANK_PROJECT_ID ?? "";

// Sandbox VM template configuration
const VM_TEMPLATE = {
  name: "forge-sandbox",
  type: "combined" as const,
  billing: { deploymentPlan: "nf-compute-50" },
  deployment: {
    instances: 1,
    docker: {
      image: "forge/sandbox-runtime:latest",
      configType: "default" as const,
    },
  },
  ports: [
    { name: "dev-server", internalPort: 3000, public: true, protocol: "HTTP" as const },
    { name: "hmr", internalPort: 24678, public: true, protocol: "HTTP" as const },
  ],
};

async function northflankRequest<T>(
  method: "GET" | "POST" | "PUT" | "DELETE",
  path: string,
  body?: Record<string, unknown>,
): Promise<T> {
  const url = `${API_BASE}${path}`;

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    Authorization: `Bearer ${API_KEY}`,
  };

  const response = await fetch(url, {
    method,
    headers,
    body: body ? JSON.stringify(body) : undefined,
  });

  if (!response.ok) {
    const text = await response.text().catch(() => "unknown error");
    throw new Error(
      `Northflank ${method} ${path} failed (${response.status}): ${text}`,
    );
  }

  return response.json() as Promise<T>;
}

// ── VM Operations ──────────────────────────────────────────────────────

/**
 * Create a new Firecracker VM from the sandbox template.
 * Returns the VM info once provisioned.
 */
export async function createVM(
  sandboxId: string,
): Promise<VMInfo> {
  const result = await northflankRequest<NorthflankCreateResponse>(
    "POST",
    `/projects/${PROJECT_ID}/services/create`,
    {
      ...VM_TEMPLATE,
      name: `forge-sandbox-${sandboxId.slice(0, 8)}`,
      deployment: {
        ...VM_TEMPLATE.deployment,
        docker: {
          ...VM_TEMPLATE.deployment.docker,
        },
      },
    },
  );

  return {
    id: result.data.id,
    status: result.data.status,
    url: result.data.dns.publicUrl,
    port: result.data.ports[0]?.number ?? 3000,
  };
}

/**
 * Start an existing (paused/stopped) VM.
 */
export async function startVM(vmId: string): Promise<void> {
  await northflankRequest<NorthflankActionResponse>(
    "POST",
    `/projects/${PROJECT_ID}/services/${vmId}/resume`,
  );
}

/**
 * Gracefully stop a VM (freeze state).
 */
export async function stopVM(vmId: string): Promise<void> {
  await northflankRequest<NorthflankActionResponse>(
    "POST",
    `/projects/${PROJECT_ID}/services/${vmId}/pause`,
  );
}

/**
 * Permanently destroy a VM and release resources.
 */
export async function destroyVM(vmId: string): Promise<void> {
  await northflankRequest<NorthflankActionResponse>(
    "DELETE",
    `/projects/${PROJECT_ID}/services/${vmId}`,
  );
}

/**
 * Poll the health endpoint on a sandbox VM until it returns 200
 * or the timeout expires. Default timeout: 60 seconds.
 */
export async function waitForHealth(
  vmUrl: string,
  timeoutMs: number = 60_000,
): Promise<boolean> {
  const startedAt = Date.now();
  const healthUrl = `${vmUrl}/health`;

  while (Date.now() - startedAt < timeoutMs) {
    try {
      const response = await fetch(healthUrl, {
        signal: AbortSignal.timeout(5_000),
      });
      if (response.ok) return true;
    } catch {
      // VM not ready yet — retry
    }
    await new Promise((resolve) => setTimeout(resolve, 2_000));
  }

  return false;
}

/**
 * Delete all R2 files associated with a sandbox (cleanup on destroy).
 */
export async function cleanupR2Files(sandboxId: string): Promise<void> {
  const forgeApiUrl =
    process.env.FORGE_INTERNAL_API_URL ?? "http://localhost:8000";
  const internalSecret = process.env.FORGE_INTERNAL_SECRET ?? "";

  await fetch(
    `${forgeApiUrl}/api/v1/internal/sandboxes/${sandboxId}/cleanup`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Internal-Secret": internalSecret,
      },
    },
  );
}

/**
 * FORGE internal API client — used by Trigger.dev jobs
 * to call back into the FORGE backend.
 *
 * Auth: X-Internal-Secret header for service-to-service calls.
 * All methods are typed and throw on non-2xx responses.
 */

// ── Types ──────────────────────────────────────────────────────────────

interface PipelineStatusUpdate {
  status: "queued" | "running" | "completed" | "failed" | "cancelled";
  currentStage?: number;
  errors?: string[];
}

interface PipelineExecutePayload {
  pipelineId: string;
  projectId: string;
  userId: string;
  ideaSpec: Record<string, unknown>;
}

interface PipelineExecuteResult {
  status: string;
  currentStage: number;
  gateResults: Record<string, { passed: boolean; reason: string }>;
  errors: string[];
  generatedFilesCount: number;
}

interface BuildStatusUpdate {
  status: "pending" | "building" | "succeeded" | "failed";
  errorSummary?: string;
}

interface BuildExecutePayload {
  buildId: string;
  projectId: string;
}

interface BuildExecuteResult {
  status: string;
  snapshotUrls: string[];
  errors: string[];
}

interface SandboxStatusUpdate {
  status: "warming" | "ready" | "assigned" | "terminating" | "terminated";
  vmId?: string;
  vmUrl?: string;
  port?: number;
}

interface WarmPoolStatus {
  warmCount: number;
  target: number;
  deficit: number;
}

interface ProvisionResult {
  sandboxId: string;
  vmId: string;
  status: string;
}

interface IdeaGeneratePayload {
  sessionId: string;
  userId: string;
  answers: Record<string, unknown>;
}

interface IdeaGenerateResult {
  ideas: Array<{
    id: string;
    title: string;
    description: string;
  }>;
  count: number;
}

// ── Client ─────────────────────────────────────────────────────────────

const BASE_URL =
  process.env.FORGE_INTERNAL_API_URL ?? "http://localhost:8000";
const INTERNAL_SECRET = process.env.FORGE_INTERNAL_SECRET ?? "";

async function request<T>(
  method: "GET" | "POST" | "PUT" | "PATCH",
  path: string,
  body?: Record<string, unknown>,
): Promise<T> {
  const url = `${BASE_URL}${path}`;

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    "X-Internal-Secret": INTERNAL_SECRET,
  };

  const response = await fetch(url, {
    method,
    headers,
    body: body ? JSON.stringify(body) : undefined,
  });

  if (!response.ok) {
    const text = await response.text().catch(() => "unknown error");
    throw new Error(
      `FORGE API ${method} ${path} failed (${response.status}): ${text}`,
    );
  }

  return response.json() as Promise<T>;
}

// ── Pipeline ───────────────────────────────────────────────────────────

export async function updatePipelineStatus(
  pipelineId: string,
  update: PipelineStatusUpdate,
): Promise<void> {
  await request<{ ok: boolean }>(
    "PATCH",
    `/api/v1/internal/pipeline/${pipelineId}/status`,
    {
      status: update.status,
      current_stage: update.currentStage,
      errors: update.errors,
    },
  );
}

export async function executePipeline(
  payload: PipelineExecutePayload,
): Promise<PipelineExecuteResult> {
  return request<PipelineExecuteResult>(
    "POST",
    "/api/v1/internal/pipeline/execute",
    {
      pipeline_id: payload.pipelineId,
      project_id: payload.projectId,
      user_id: payload.userId,
      idea_spec: payload.ideaSpec,
    },
  );
}

// ── Project ────────────────────────────────────────────────────────────

export async function updateProjectStatus(
  projectId: string,
  status: "draft" | "building" | "live" | "error",
): Promise<void> {
  await request<{ ok: boolean }>(
    "PATCH",
    `/api/v1/internal/projects/${projectId}/status`,
    { status },
  );
}

// ── Build ──────────────────────────────────────────────────────────────

export async function updateBuildStatus(
  buildId: string,
  update: BuildStatusUpdate,
): Promise<void> {
  await request<{ ok: boolean }>(
    "PATCH",
    `/api/v1/internal/builds/${buildId}/status`,
    {
      status: update.status,
      error_summary: update.errorSummary,
    },
  );
}

export async function executeBuild(
  payload: BuildExecutePayload,
): Promise<BuildExecuteResult> {
  return request<BuildExecuteResult>(
    "POST",
    "/api/v1/internal/builds/execute",
    {
      build_id: payload.buildId,
      project_id: payload.projectId,
    },
  );
}

// ── Sandbox ────────────────────────────────────────────────────────────

export async function updateSandboxStatus(
  sandboxId: string,
  update: SandboxStatusUpdate,
): Promise<void> {
  await request<{ ok: boolean }>(
    "PATCH",
    `/api/v1/internal/sandboxes/${sandboxId}/status`,
    {
      status: update.status,
      vm_id: update.vmId,
      vm_url: update.vmUrl,
      port: update.port,
    },
  );
}

export async function countWarmSandboxes(): Promise<WarmPoolStatus> {
  return request<WarmPoolStatus>(
    "GET",
    "/api/v1/internal/sandboxes/pool-status",
  );
}

export async function provisionSandbox(): Promise<ProvisionResult> {
  return request<ProvisionResult>(
    "POST",
    "/api/v1/internal/sandboxes/provision",
  );
}

// ── Ideation ───────────────────────────────────────────────────────────

export async function generateIdeas(
  payload: IdeaGeneratePayload,
): Promise<IdeaGenerateResult> {
  return request<IdeaGenerateResult>(
    "POST",
    "/api/v1/internal/ideation/generate",
    {
      session_id: payload.sessionId,
      user_id: payload.userId,
      answers: payload.answers,
    },
  );
}

export async function completeIdeaSession(
  sessionId: string,
): Promise<void> {
  await request<{ ok: boolean }>(
    "PATCH",
    `/api/v1/internal/ideation/sessions/${sessionId}/complete`,
  );
}

export async function failIdeaSession(
  sessionId: string,
  error: string,
): Promise<void> {
  await request<{ ok: boolean }>(
    "PATCH",
    `/api/v1/internal/ideation/sessions/${sessionId}/fail`,
    { error },
  );
}

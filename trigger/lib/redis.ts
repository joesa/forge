/**
 * Redis pub/sub client for Trigger.dev jobs.
 *
 * Publishes progress events so the FORGE WebSocket layer can
 * relay them to connected frontend clients in real time.
 */

import Redis from "ioredis";

// ── Singleton ──────────────────────────────────────────────────────────

let _client: Redis | null = null;

function getRedis(): Redis {
  if (!_client) {
    const url = process.env.REDIS_URL ?? "redis://127.0.0.1:6379";
    _client = new Redis(url, {
      maxRetriesPerRequest: 3,
      connectTimeout: 5_000,
      lazyConnect: true,
    });

    _client.on("error", (err) => {
      console.error("[FORGE Redis] Connection error:", err.message);
    });
  }
  return _client;
}

// ── Publish ────────────────────────────────────────────────────────────

export interface PipelineEvent {
  pipelineId: string;
  stage: number;
  status: string;
  detail: string;
  timestamp?: string;
  agentId?: string;
  progress?: number;
}

export interface ConsoleEvent {
  level: "info" | "warn" | "error" | "debug";
  message: string;
  timestamp: string;
  source?: string;
}

/**
 * Publish a pipeline progress event to the `pipeline:{id}` channel.
 */
export async function publishPipelineEvent(
  pipelineId: string,
  event: Omit<PipelineEvent, "pipelineId" | "timestamp">,
): Promise<void> {
  const redis = getRedis();
  const channel = `pipeline:${pipelineId}`;
  const payload: PipelineEvent = {
    ...event,
    pipelineId,
    timestamp: new Date().toISOString(),
  };
  await redis.publish(channel, JSON.stringify(payload));
}

/**
 * Publish a build progress event.
 */
export async function publishBuildEvent(
  buildId: string,
  event: { status: string; detail: string; agentIndex?: number },
): Promise<void> {
  const redis = getRedis();
  const channel = `build:${buildId}`;
  await redis.publish(
    channel,
    JSON.stringify({
      buildId,
      ...event,
      timestamp: new Date().toISOString(),
    }),
  );
}

/**
 * Publish a console log entry for a sandbox.
 */
export async function publishConsoleEvent(
  sandboxId: string,
  event: ConsoleEvent,
): Promise<void> {
  const redis = getRedis();
  const channel = `console:${sandboxId}`;
  await redis.publish(channel, JSON.stringify(event));
}

/**
 * Clean up the Redis connection (call during graceful shutdown).
 */
export async function closeRedis(): Promise<void> {
  if (_client) {
    await _client.quit();
    _client = null;
  }
}

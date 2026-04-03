/**
 * FORGE — Trigger.dev v3 project configuration.
 *
 * Scans ./jobs for durable task definitions.
 * Global retry policy: 3 attempts with exponential backoff.
 */

import { defineConfig } from "@trigger.dev/sdk/v3";

export default defineConfig({
  project: process.env.TRIGGER_PROJECT_ID ?? "forge-dev",

  dirs: ["./jobs"],

  runtime: "node",

  maxDuration: 3600,

  retries: {
    enabledInDev: false,
    default: {
      maxAttempts: 3,
      minTimeoutInMs: 1_000,
      maxTimeoutInMs: 30_000,
      factor: 2,
      randomize: true,
    },
  },
});

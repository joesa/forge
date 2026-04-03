/**
 * idea-generation — AI idea generation job.
 *
 * Runs 5 parallel AI calls using all 8 C-Suite agent perspectives
 * to produce 5 unique, high-value application ideas. Stores results
 * in the ideas table and marks the idea_session as completed.
 *
 * Max duration: 2 minutes (AI calls are fast, 5 in parallel).
 */

import { task } from "@trigger.dev/sdk/v3";
import {
  generateIdeas,
  completeIdeaSession,
  failIdeaSession,
} from "../lib/api-client.js";
import { publishPipelineEvent, closeRedis } from "../lib/redis.js";

// ── Payload type ───────────────────────────────────────────────────────

interface IdeaGenerationPayload {
  sessionId: string;
  userId: string;
  answers: Record<string, unknown>;
}

// ── Job definition ─────────────────────────────────────────────────────

export const ideaGenerationJob = task({
  id: "idea-generation",
  maxDuration: 120, // 2 minutes max

  retry: {
    maxAttempts: 3,
    minTimeoutInMs: 2_000,
    maxTimeoutInMs: 15_000,
    factor: 2,
  },

  run: async (payload: IdeaGenerationPayload, { ctx }) => {
    const { sessionId, userId, answers } = payload;
    const runId = ctx.run.id;

    console.log(
      `[idea-generation] Starting session=${sessionId} user=${userId} run=${runId}`,
    );

    // Publish start event (frontend can subscribe for progress)
    await publishPipelineEvent(sessionId, {
      stage: 0,
      status: "generating",
      detail: "Generating 5 unique ideas using C-Suite agent perspectives",
    });

    // ── Step 1: Call the ideation generation endpoint ──────────────
    // The backend handles:
    //   - 5 parallel AI calls with different creative angles
    //   - All 8 C-Suite agent perspectives injected as system context
    //   - Storing generated ideas in the `ideas` table
    const result = await generateIdeas({ sessionId, userId, answers });

    console.log(
      `[idea-generation] Generated ${result.count} ideas for session=${sessionId}`,
    );

    // ── Step 2: Mark session as completed ──────────────────────────
    await completeIdeaSession(sessionId);

    // ── Step 3: Publish completion event ───────────────────────────
    await publishPipelineEvent(sessionId, {
      stage: 0,
      status: "completed",
      detail: `Generated ${result.count} unique ideas`,
    });

    console.log(
      `[idea-generation] Session ${sessionId} completed successfully`,
    );

    await closeRedis();

    return {
      status: "completed",
      sessionId,
      ideaCount: result.count,
      ideas: result.ideas.map((idea) => ({
        id: idea.id,
        title: idea.title,
      })),
    };
  },

  onFailure: async (payload, error) => {
    const { sessionId } = payload as IdeaGenerationPayload;
    const errorMessage =
      error instanceof Error ? error.message : String(error);

    console.error(
      `[idea-generation] FATAL failure for session=${sessionId}: ${errorMessage}`,
    );

    // Mark session as failed in DB (prevents stuck 'active' sessions)
    try {
      await failIdeaSession(sessionId, errorMessage);
    } catch (dbError) {
      console.error(
        "[idea-generation] Failed to mark session as failed:",
        dbError,
      );
    }

    try {
      await publishPipelineEvent(sessionId, {
        stage: 0,
        status: "failed",
        detail: `Idea generation failed: ${errorMessage}`,
      });
    } catch (redisError) {
      console.error(
        "[idea-generation] Failed to publish failure event:",
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

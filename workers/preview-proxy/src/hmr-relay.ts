/**
 * PreviewHMR — Durable Object for HMR WebSocket relay.
 *
 * Bridges the browser ↔ sandbox WebSocket connection for Vite/Next.js HMR.
 * Each sandbox gets its own Durable Object instance (keyed by sandbox_id).
 *
 * Features:
 *   - Bidirectional WebSocket relay (browser ↔ sandbox)
 *   - Exponential backoff reconnection (1s, 2s, 4s, … max 30s, 5 attempts)
 *   - 30s reconnect window when browser disconnects
 *   - Server-restart notifications to browser on sandbox disconnect
 *
 * Architecture target: file save → browser update under 700ms (AGENTS.md rule #10)
 */

import type { Env } from "./env";

// ── Constants ──────────────────────────────────────────────────────

const DEFAULT_HMR_PORT = 24678; // Vite default
const MAX_RECONNECT_ATTEMPTS = 5;
const MAX_RECONNECT_DELAY_MS = 30_000;
const BROWSER_RECONNECT_WINDOW_MS = 30_000;

// ── Durable Object ─────────────────────────────────────────────────

export class PreviewHMR implements DurableObject {
  private browserWs: WebSocket | null = null;
  private sandboxWs: WebSocket | null = null;
  private sandboxUrl = "";
  private reconnectAttempts = 0;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private browserDisconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private state: DurableObjectState;

  constructor(state: DurableObjectState, _env: Env) {
    this.state = state;
  }

  /**
   * Handle incoming fetch — upgrade browser connection and connect to sandbox.
   *
   * The sandbox_url is passed via a custom header from the main Worker.
   */
  async fetch(request: Request): Promise<Response> {
    const sandboxUrl = request.headers.get("X-Sandbox-URL");
    if (!sandboxUrl) {
      return new Response(
        JSON.stringify({ error: "Missing sandbox URL" }),
        { status: 400, headers: { "Content-Type": "application/json" } },
      );
    }

    // Store sandbox URL for reconnection
    this.sandboxUrl = sandboxUrl;

    // Clean up any previous connections
    this.cleanup();

    // Step 1: Upgrade browser connection using WebSocket pair
    const pair = new WebSocketPair();
    const [clientWs, serverWs] = [pair[0], pair[1]];

    serverWs.accept();
    this.browserWs = serverWs;

    // Step 2: Connect to sandbox HMR endpoint
    const sandboxHost = new URL(this.sandboxUrl).host;
    const hmrUrl = `wss://${sandboxHost}:${DEFAULT_HMR_PORT}`;
    await this.connectToSandbox(hmrUrl);

    // Step 3: Set up browser → sandbox relay
    serverWs.addEventListener("message", (event: MessageEvent) => {
      if (
        this.sandboxWs &&
        this.sandboxWs.readyState === WebSocket.READY_STATE_OPEN
      ) {
        this.sandboxWs.send(
          typeof event.data === "string"
            ? event.data
            : event.data as ArrayBuffer,
        );
      }
    });

    // Step 4: Handle browser disconnect
    serverWs.addEventListener("close", () => {
      this.browserWs = null;

      // Keep sandbox connection alive for 30s (reconnect window)
      this.browserDisconnectTimer = setTimeout(() => {
        if (
          !this.browserWs ||
          this.browserWs.readyState !== WebSocket.READY_STATE_OPEN
        ) {
          this.sandboxWs?.close();
          this.sandboxWs = null;
          this.clearReconnectTimer();
        }
      }, BROWSER_RECONNECT_WINDOW_MS);
    });

    serverWs.addEventListener("error", () => {
      this.browserWs = null;
    });

    // Return the client side of the WebSocket pair to the browser
    return new Response(null, {
      status: 101,
      webSocket: clientWs,
    });
  }

  /**
   * Connect to the sandbox HMR WebSocket and wire up relay + reconnection.
   */
  private async connectToSandbox(hmrUrl: string): Promise<void> {
    try {
      const ws = new WebSocket(hmrUrl);
      this.sandboxWs = ws;

      // Sandbox → browser relay
      ws.addEventListener("message", (event: MessageEvent) => {
        if (
          this.browserWs &&
          this.browserWs.readyState === WebSocket.READY_STATE_OPEN
        ) {
          this.browserWs.send(
            typeof event.data === "string"
              ? event.data
              : event.data as ArrayBuffer,
          );
        }
      });

      // Handle sandbox disconnect — notify browser and attempt reconnect
      ws.addEventListener("close", () => {
        this.sandboxWs = null;

        // Notify browser that the server restarted
        if (
          this.browserWs &&
          this.browserWs.readyState === WebSocket.READY_STATE_OPEN
        ) {
          this.browserWs.send(
            JSON.stringify({ type: "server-restart" }),
          );
        }

        // Attempt reconnection with exponential backoff
        this.reconnect(hmrUrl);
      });

      ws.addEventListener("error", () => {
        // error is followed by close, so reconnect happens there
      });

      ws.addEventListener("open", () => {
        // Reset reconnect counter on successful connection
        this.reconnectAttempts = 0;
      });
    } catch {
      // Connection failed — attempt reconnect
      this.reconnect(hmrUrl);
    }
  }

  /**
   * Reconnect to sandbox HMR with exponential backoff.
   * Schedule: 1s, 2s, 4s, 8s, 16s (capped at 30s), max 5 attempts.
   */
  private reconnect(hmrUrl: string): void {
    if (this.reconnectAttempts >= MAX_RECONNECT_ATTEMPTS) {
      // Give up — notify browser
      if (
        this.browserWs &&
        this.browserWs.readyState === WebSocket.READY_STATE_OPEN
      ) {
        this.browserWs.send(
          JSON.stringify({
            type: "custom",
            event: "hmr-reconnect-failed",
            data: { attempts: this.reconnectAttempts },
          }),
        );
      }
      return;
    }

    const delay = Math.min(
      1000 * Math.pow(2, this.reconnectAttempts),
      MAX_RECONNECT_DELAY_MS,
    );
    this.reconnectAttempts++;

    this.reconnectTimer = setTimeout(() => {
      void this.connectToSandbox(hmrUrl);
    }, delay);
  }

  /**
   * Clean up all connections and timers.
   */
  private cleanup(): void {
    this.clearReconnectTimer();

    if (this.browserDisconnectTimer) {
      clearTimeout(this.browserDisconnectTimer);
      this.browserDisconnectTimer = null;
    }

    if (
      this.browserWs &&
      this.browserWs.readyState === WebSocket.READY_STATE_OPEN
    ) {
      this.browserWs.close(1000, "New connection replacing old");
    }
    this.browserWs = null;

    if (
      this.sandboxWs &&
      this.sandboxWs.readyState === WebSocket.READY_STATE_OPEN
    ) {
      this.sandboxWs.close(1000, "Cleanup");
    }
    this.sandboxWs = null;

    this.reconnectAttempts = 0;
  }

  /**
   * Clear the reconnect timer if active.
   */
  private clearReconnectTimer(): void {
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
  }
}

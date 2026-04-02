/**
 * forge-preview-proxy — Main Cloudflare Worker entry point.
 *
 * Routes *.preview.forge.dev traffic to Northflank sandboxes.
 * Every preview URL flows through this Worker:
 *
 *   1. Extract sandbox_id from subdomain
 *   2. Authenticate (JWT cookie OR HMAC share token)
 *   3. Look up sandbox URL from Workers KV
 *   4. Delegate WebSocket (HMR) to Durable Object
 *   5. Proxy HTTP requests to sandbox
 *
 * Architecture:
 *   - Cloudflare Worker at *.preview.forge.dev (AGENTS.md)
 *   - Cloudflare Durable Objects for HMR relay + state
 *   - Cloudflare KV for sandbox URL registry
 *   - Target: file save → browser update under 700ms
 */

import { parseCookie, validateJWT, validateShareToken } from "./auth";
import type { Env } from "./env";

export { PreviewHMR } from "./hmr-relay";

// ── Constants ──────────────────────────────────────────────────────

const CORS_METHODS = "GET, POST, PUT, DELETE, PATCH, OPTIONS";
const CORS_ALLOWED_HEADERS = "Content-Type, Authorization, X-Requested-With";

/**
 * Build CORS headers using the actual request origin.
 * Wildcard + credentials is invalid per CORS spec — browsers ignore it.
 */
function buildCorsHeaders(requestOrigin: string | null): Record<string, string> {
  const origin = requestOrigin ?? "https://forge.dev";
  return {
    "Access-Control-Allow-Origin": origin,
    "Access-Control-Allow-Methods": CORS_METHODS,
    "Access-Control-Allow-Headers": CORS_ALLOWED_HEADERS,
    "Access-Control-Allow-Credentials": "true",
    "Vary": "Origin",
  };
}

const JWT_COOKIE_NAME = "forge_access_token";

// ── Helpers ────────────────────────────────────────────────────────

/**
 * Create a JSON error response with CORS headers.
 */
function errorResponse(
  message: string,
  status: number,
  requestOrigin: string | null = null,
): Response {
  return new Response(
    JSON.stringify({ error: message }),
    {
      status,
      headers: {
        "Content-Type": "application/json",
        ...buildCorsHeaders(requestOrigin),
      },
    },
  );
}

/**
 * Extract sandbox_id from the request hostname.
 * Hostname format: "{sandbox_id}.preview.forge.dev"
 */
function extractSandboxId(hostname: string): string | null {
  // Split on dots and take the first segment
  const parts = hostname.split(".");
  // Expect at least 4 parts: sandbox_id.preview.forge.dev
  if (parts.length < 4) {
    return null;
  }
  const sandboxId = parts[0];
  // Validate: must be non-empty and look like a valid ID
  if (!sandboxId || sandboxId.length === 0) {
    return null;
  }
  return sandboxId;
}

// ── Main Worker ────────────────────────────────────────────────────

const worker: ExportedHandler<Env> = {
  async fetch(
    request: Request,
    env: Env,
    _ctx: ExecutionContext,
  ): Promise<Response> {
    const requestOrigin = request.headers.get("Origin");

    // Handle CORS preflight
    if (request.method === "OPTIONS") {
      return new Response(null, {
        status: 204,
        headers: buildCorsHeaders(requestOrigin),
      });
    }

    try {
      // ── Step 1: Extract sandbox_id from subdomain ──────────────
      const url = new URL(request.url);
      const sandboxId = extractSandboxId(url.hostname);

      if (!sandboxId) {
        return errorResponse("Not found", 404, requestOrigin);
      }

      // ── Step 2: Authenticate the request ───────────────────────
      let authenticated = false;

      // Method A: JWT cookie (forge_access_token)
      const cookieHeader = request.headers.get("Cookie");
      if (cookieHeader) {
        const jwtToken = parseCookie(cookieHeader, JWT_COOKIE_NAME);
        if (jwtToken) {
          const result = await validateJWT(
            jwtToken,
            env.NHOST_JWKS_URL,
            env.SANDBOX_URLS, // Reuse KV for JWKS cache
          );
          if (result.valid) {
            authenticated = true;
          }
        }
      }

      // Method B: HMAC share token (?token= with optional &expires_at=)
      // Backend stores share data in KV at "preview_share:{token}"
      // with {sandbox_id, expires_at, user_id}.
      // The share URL may include expires_at explicitly, or we look it up.
      if (!authenticated) {
        const token = url.searchParams.get("token");

        if (token) {
          let expiresAt: number | null = null;

          // Try explicit expires_at param first
          const expiresAtStr = url.searchParams.get("expires_at");
          if (expiresAtStr) {
            const parsed = parseInt(expiresAtStr, 10);
            if (!isNaN(parsed)) {
              expiresAt = parsed;
            }
          }

          // If no explicit expires_at, look up from KV (backend stores it)
          if (expiresAt === null) {
            const shareData = await env.SANDBOX_URLS.get(`preview_share:${token}`);
            if (shareData) {
              try {
                const parsed = JSON.parse(shareData) as {
                  sandbox_id?: string;
                  expires_at?: string;
                };
                if (parsed.expires_at) {
                  const isoDate = new Date(parsed.expires_at);
                  expiresAt = Math.floor(isoDate.getTime() / 1000);
                }
              } catch {
                // Invalid JSON in KV — ignore
              }
            }
          }

          if (expiresAt !== null) {
            const valid = await validateShareToken(
              token,
              sandboxId,
              expiresAt,
              env.HMAC_SECRET,
            );
            if (valid) {
              authenticated = true;
            }
          }
        }
      }

      if (!authenticated) {
        return errorResponse("Unauthorized", 401, requestOrigin);
      }

      // ── Step 3: Look up sandbox URL from Workers KV ────────────
      const kvKey = `sandbox:${sandboxId}:url`;
      const sandboxUrl = await env.SANDBOX_URLS.get(kvKey);

      if (!sandboxUrl) {
        return errorResponse("Sandbox not running", 404, requestOrigin);
      }

      // ── Step 4: Handle WebSocket (HMR) → Durable Object ────────
      const upgradeHeader = request.headers.get("Upgrade");
      if (upgradeHeader && upgradeHeader.toLowerCase() === "websocket") {
        const doId = env.PREVIEW_HMR.idFromName(sandboxId);
        const stub = env.PREVIEW_HMR.get(doId);

        // Forward the request with sandbox URL as a custom header
        const doRequest = new Request(request.url, {
          method: request.method,
          headers: new Headers([
            ...Array.from(request.headers.entries()),
            ["X-Sandbox-URL", sandboxUrl],
          ]),
        });

        return stub.fetch(doRequest);
      }

      // ── Step 5: Proxy HTTP request to sandbox ──────────────────
      const proxyUrl =
        sandboxUrl + url.pathname + (url.search ? url.search : "");

      // Build proxy headers — forward all original headers but strip
      // host and cookie (sandbox doesn't need auth cookies)
      const proxyHeaders = new Headers(request.headers);
      proxyHeaders.delete("Host");
      proxyHeaders.delete("Cookie");
      proxyHeaders.set("X-Forwarded-For",
        request.headers.get("CF-Connecting-IP") ?? "unknown",
      );
      proxyHeaders.set("X-Forwarded-Proto", url.protocol.replace(":", ""));
      proxyHeaders.set("X-Forwarded-Host", url.hostname);
      proxyHeaders.set("X-Sandbox-ID", sandboxId);

      const proxied = await fetch(proxyUrl, {
        method: request.method,
        headers: proxyHeaders,
        body:
          request.method !== "GET" && request.method !== "HEAD"
            ? request.body
            : undefined,
      });

      // Build response with CORS headers merged
      const responseHeaders = new Headers(proxied.headers);
      const corsHeaders = buildCorsHeaders(requestOrigin);
      for (const [key, value] of Object.entries(corsHeaders)) {
        responseHeaders.set(key, value);
      }

      return new Response(proxied.body, {
        status: proxied.status,
        statusText: proxied.statusText,
        headers: responseHeaders,
      });
    } catch (err: unknown) {
      const message =
        err instanceof Error ? err.message : "Internal server error";
      console.error("Preview proxy error:", message);
      return errorResponse("Internal server error", 500, request.headers.get("Origin"));
    }
  },
};

export default worker;

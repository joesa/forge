/**
 * Unit tests for auth.ts — JWT validation and HMAC share token validation.
 *
 * Uses vitest with mock crypto for deterministic testing.
 * Rule: Never call real external APIs in tests (AGENTS.md rule #7).
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import {
  parseCookie,
  validateJWT,
  validateShareToken,
} from "../src/auth";

// ── Test Helpers ───────────────────────────────────────────────────

/**
 * Create a base64url-encoded string.
 */
function base64urlEncode(input: string): string {
  const encoded = btoa(input);
  return encoded.replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

/**
 * Create a fake JWT with the given payload (signature is garbage).
 */
function createFakeJWT(
  header: Record<string, unknown>,
  payload: Record<string, unknown>,
): string {
  const headerB64 = base64urlEncode(JSON.stringify(header));
  const payloadB64 = base64urlEncode(JSON.stringify(payload));
  const signatureB64 = base64urlEncode("fake-signature-bytes");
  return `${headerB64}.${payloadB64}.${signatureB64}`;
}

// ── Mock KV Namespace ──────────────────────────────────────────────

function createMockKV(): KVNamespace {
  const store = new Map<string, string>();
  return {
    get: vi.fn(async (key: string) => store.get(key) ?? null),
    put: vi.fn(async (key: string, value: string) => {
      store.set(key, value);
    }),
    delete: vi.fn(async () => undefined),
    list: vi.fn(async () => ({ keys: [], list_complete: true, cacheStatus: null })),
    getWithMetadata: vi.fn(async () => ({ value: null, metadata: null, cacheStatus: null })),
  } as unknown as KVNamespace;
}

// ── parseCookie tests ──────────────────────────────────────────────

describe("parseCookie", () => {
  it("extracts a cookie by name", () => {
    const header = "forge_access_token=abc123; session_id=xyz";
    expect(parseCookie(header, "forge_access_token")).toBe("abc123");
    expect(parseCookie(header, "session_id")).toBe("xyz");
  });

  it("returns undefined for missing cookie", () => {
    const header = "other_cookie=value";
    expect(parseCookie(header, "forge_access_token")).toBeUndefined();
  });

  it("handles empty cookie header", () => {
    expect(parseCookie("", "forge_access_token")).toBeUndefined();
  });

  it("handles cookies with = in value", () => {
    const header = "token=abc=def=ghi; other=1";
    expect(parseCookie(header, "token")).toBe("abc=def=ghi");
  });

  it("handles whitespace around cookies", () => {
    const header = "  forge_access_token = hello ; other = world ";
    // Name has internal space due to split — our parser trims correctly
    expect(parseCookie(header, "forge_access_token")).toBe("hello");
  });

  it("handles single cookie with no semicolons", () => {
    const header = "forge_access_token=single_value";
    expect(parseCookie(header, "forge_access_token")).toBe("single_value");
  });
});

// ── validateJWT tests ──────────────────────────────────────────────

describe("validateJWT", () => {
  let mockKV: KVNamespace;

  beforeEach(() => {
    mockKV = createMockKV();
  });

  it("rejects malformed JWT (not 3 parts)", async () => {
    const result = await validateJWT(
      "not.a.valid.jwt.at.all",
      "https://auth.nhost.run/.well-known/jwks.json",
      mockKV,
    );
    expect(result.valid).toBe(false);
    expect(result.user_id).toBe("");
  });

  it("rejects JWT with empty string", async () => {
    const result = await validateJWT(
      "",
      "https://auth.nhost.run/.well-known/jwks.json",
      mockKV,
    );
    expect(result.valid).toBe(false);
  });

  it("rejects JWT with unsupported algorithm", async () => {
    const token = createFakeJWT(
      { alg: "HS256", typ: "JWT" },
      { sub: "user-123", exp: Math.floor(Date.now() / 1000) + 3600 },
    );

    const result = await validateJWT(
      token,
      "https://auth.nhost.run/.well-known/jwks.json",
      mockKV,
    );
    expect(result.valid).toBe(false);
  });

  it("rejects JWT when JWKS fetch fails", async () => {
    // Mock global fetch to fail
    const originalFetch = globalThis.fetch;
    globalThis.fetch = vi.fn().mockRejectedValue(new Error("Network error"));

    const token = createFakeJWT(
      { alg: "RS256", typ: "JWT", kid: "key-1" },
      { sub: "user-123", exp: Math.floor(Date.now() / 1000) + 3600 },
    );

    const result = await validateJWT(
      token,
      "https://auth.nhost.run/.well-known/jwks.json",
      mockKV,
    );
    expect(result.valid).toBe(false);

    globalThis.fetch = originalFetch;
  });

  it("rejects JWT when no matching key found in JWKS", async () => {
    const originalFetch = globalThis.fetch;
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        keys: [
          { kty: "RSA", kid: "other-key", alg: "RS256", use: "sig", n: "abc", e: "AQAB" },
        ],
      }),
    });

    const token = createFakeJWT(
      { alg: "RS256", typ: "JWT", kid: "non-existent-key" },
      { sub: "user-123", exp: Math.floor(Date.now() / 1000) + 3600 },
    );

    const result = await validateJWT(
      token,
      "https://auth.nhost.run/.well-known/jwks.json",
      mockKV,
    );
    expect(result.valid).toBe(false);

    globalThis.fetch = originalFetch;
  });

  it("caches JWKS in KV after first fetch", async () => {
    const originalFetch = globalThis.fetch;
    const jwksData = {
      keys: [
        { kty: "RSA", kid: "key-1", alg: "RS256", use: "sig", n: "abc", e: "AQAB" },
      ],
    };

    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => jwksData,
    });

    const token = createFakeJWT(
      { alg: "RS256", typ: "JWT", kid: "key-1" },
      { sub: "user-123", exp: Math.floor(Date.now() / 1000) + 3600 },
    );

    // First call fetches from network
    await validateJWT(
      token,
      "https://auth.nhost.run/.well-known/jwks.json",
      mockKV,
    );

    // KV.put should have been called with the JWKS data
    expect(mockKV.put).toHaveBeenCalledWith(
      "jwks:nhost:keys",
      JSON.stringify(jwksData),
      { expirationTtl: 3600 },
    );

    globalThis.fetch = originalFetch;
  });

  it("uses cached JWKS from KV when available", async () => {
    const originalFetch = globalThis.fetch;
    const jwksData = {
      keys: [
        { kty: "RSA", kid: "key-1", alg: "RS256", use: "sig", n: "abc", e: "AQAB" },
      ],
    };

    // Pre-populate the KV cache
    await mockKV.put("jwks:nhost:keys", JSON.stringify(jwksData));

    const fetchMock = vi.fn();
    globalThis.fetch = fetchMock;

    const token = createFakeJWT(
      { alg: "RS256", typ: "JWT", kid: "key-1" },
      { sub: "user-123", exp: Math.floor(Date.now() / 1000) + 3600 },
    );

    await validateJWT(
      token,
      "https://auth.nhost.run/.well-known/jwks.json",
      mockKV,
    );

    // fetch should NOT have been called since KV had the cached value
    expect(fetchMock).not.toHaveBeenCalled();

    globalThis.fetch = originalFetch;
  });

  it("rejects JWT without exp claim (no expiration = reject)", async () => {
    const originalFetch = globalThis.fetch;
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        keys: [
          { kty: "RSA", kid: "key-1", alg: "RS256", use: "sig", n: "abc", e: "AQAB" },
        ],
      }),
    });

    // JWT with NO exp claim
    const token = createFakeJWT(
      { alg: "RS256", typ: "JWT", kid: "key-1" },
      { sub: "user-123" }, // no exp!
    );

    const result = await validateJWT(
      token,
      "https://auth.nhost.run/.well-known/jwks.json",
      mockKV,
    );
    // Must be rejected — tokens without expiration are not allowed
    expect(result.valid).toBe(false);

    globalThis.fetch = originalFetch;
  });
});

// ── validateShareToken tests ───────────────────────────────────────

describe("validateShareToken", () => {
  const HMAC_SECRET = "test-hmac-secret-for-preview-shares";

  /**
   * Generate a valid HMAC token for testing, matching backend format:
   * HMAC-SHA256("{sandbox_id}:{expires_at_unix}", secret).hexdigest()
   */
  async function generateValidToken(
    sandboxId: string,
    expiresAt: number,
    secret: string,
  ): Promise<string> {
    const message = `${sandboxId}:${expiresAt}`;
    const encoder = new TextEncoder();

    const key = await crypto.subtle.importKey(
      "raw",
      encoder.encode(secret),
      { name: "HMAC", hash: "SHA-256" },
      false,
      ["sign"],
    );

    const signatureBuffer = await crypto.subtle.sign(
      "HMAC",
      key,
      encoder.encode(message),
    );

    const bytes = new Uint8Array(signatureBuffer);
    return Array.from(bytes)
      .map((b) => b.toString(16).padStart(2, "0"))
      .join("");
  }

  it("accepts a valid, non-expired token", async () => {
    const sandboxId = "abc123xyz";
    const expiresAt = Math.floor(Date.now() / 1000) + 86400; // 24h from now
    const token = await generateValidToken(sandboxId, expiresAt, HMAC_SECRET);

    const result = await validateShareToken(
      token,
      sandboxId,
      expiresAt,
      HMAC_SECRET,
    );
    expect(result).toBe(true);
  });

  it("rejects an expired token", async () => {
    const sandboxId = "abc123xyz";
    const expiresAt = Math.floor(Date.now() / 1000) - 3600; // 1h ago
    const token = await generateValidToken(sandboxId, expiresAt, HMAC_SECRET);

    const result = await validateShareToken(
      token,
      sandboxId,
      expiresAt,
      HMAC_SECRET,
    );
    expect(result).toBe(false);
  });

  it("rejects a token with wrong sandbox_id", async () => {
    const expiresAt = Math.floor(Date.now() / 1000) + 86400;
    const token = await generateValidToken(
      "correct-sandbox",
      expiresAt,
      HMAC_SECRET,
    );

    const result = await validateShareToken(
      token,
      "wrong-sandbox",
      expiresAt,
      HMAC_SECRET,
    );
    expect(result).toBe(false);
  });

  it("rejects a token with wrong secret", async () => {
    const sandboxId = "abc123xyz";
    const expiresAt = Math.floor(Date.now() / 1000) + 86400;
    const token = await generateValidToken(
      sandboxId,
      expiresAt,
      "wrong-secret",
    );

    const result = await validateShareToken(
      token,
      sandboxId,
      expiresAt,
      HMAC_SECRET,
    );
    expect(result).toBe(false);
  });

  it("rejects a tampered token", async () => {
    const sandboxId = "abc123xyz";
    const expiresAt = Math.floor(Date.now() / 1000) + 86400;
    const token = await generateValidToken(sandboxId, expiresAt, HMAC_SECRET);

    // Tamper with the token by flipping a character
    const tampered =
      token[0] === "a"
        ? "b" + token.slice(1)
        : "a" + token.slice(1);

    const result = await validateShareToken(
      tampered,
      sandboxId,
      expiresAt,
      HMAC_SECRET,
    );
    expect(result).toBe(false);
  });

  it("rejects a token with wrong expires_at", async () => {
    const sandboxId = "abc123xyz";
    const expiresAt = Math.floor(Date.now() / 1000) + 86400;
    const token = await generateValidToken(sandboxId, expiresAt, HMAC_SECRET);

    // Pass wrong expires_at
    const result = await validateShareToken(
      token,
      sandboxId,
      expiresAt + 1,
      HMAC_SECRET,
    );
    expect(result).toBe(false);
  });

  it("rejects empty token", async () => {
    const result = await validateShareToken(
      "",
      "abc123xyz",
      Math.floor(Date.now() / 1000) + 86400,
      HMAC_SECRET,
    );
    expect(result).toBe(false);
  });

  it("is deterministic — same inputs produce same token", async () => {
    const sandboxId = "deterministic-test";
    const expiresAt = Math.floor(Date.now() / 1000) + 86400; // must be in the future

    const token1 = await generateValidToken(sandboxId, expiresAt, HMAC_SECRET);
    const token2 = await generateValidToken(sandboxId, expiresAt, HMAC_SECRET);

    // Same inputs → same hex digest
    expect(token1).toBe(token2);

    // Both validate successfully with the same params
    const result1 = await validateShareToken(
      token1,
      sandboxId,
      expiresAt,
      HMAC_SECRET,
    );
    const result2 = await validateShareToken(
      token2,
      sandboxId,
      expiresAt,
      HMAC_SECRET,
    );
    expect(result1).toBe(true);
    expect(result2).toBe(true);
  });

  it("handles UUID-format sandbox IDs correctly", async () => {
    const sandboxId = "550e8400-e29b-41d4-a716-446655440000";
    const expiresAt = Math.floor(Date.now() / 1000) + 86400;
    const token = await generateValidToken(sandboxId, expiresAt, HMAC_SECRET);

    const result = await validateShareToken(
      token,
      sandboxId,
      expiresAt,
      HMAC_SECRET,
    );
    expect(result).toBe(true);
  });
});

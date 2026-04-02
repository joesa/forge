/**
 * Authentication module for forge-preview-proxy.
 *
 * Two auth methods:
 *   A. JWT cookie (forge_access_token) — validated against Nhost JWKS
 *   B. HMAC share token (?token= query param) — HMAC-SHA256 validation
 *
 * JWKS keys are cached in Workers KV for 1 hour to minimize latency.
 * Secrets are never hardcoded — always from Worker env bindings.
 */

// ── Types ──────────────────────────────────────────────────────────

export interface JWTValidationResult {
  valid: boolean;
  user_id: string;
}

interface JWKSKey {
  kty: string;
  kid: string;
  use?: string;
  alg?: string;
  n?: string;
  e?: string;
  crv?: string;
  x?: string;
  y?: string;
}

interface JWKSResponse {
  keys: JWKSKey[];
}

interface JWTHeader {
  alg: string;
  typ?: string;
  kid?: string;
}

interface JWTPayload {
  sub?: string;
  exp?: number;
  iat?: number;
  iss?: string;
  [key: string]: unknown;
}

// ── Helpers ────────────────────────────────────────────────────────

const JWKS_CACHE_KEY = "jwks:nhost:keys";
const JWKS_CACHE_TTL_SECONDS = 3600; // 1 hour

/**
 * Parse a cookie header string and return the value for a given name.
 */
export function parseCookie(
  cookieHeader: string,
  name: string,
): string | undefined {
  const cookies = cookieHeader.split(";");
  for (const cookie of cookies) {
    const trimmed = cookie.trim();
    const eqIdx = trimmed.indexOf("=");
    if (eqIdx === -1) continue;
    const cookieName = trimmed.substring(0, eqIdx).trim();
    if (cookieName === name) {
      return trimmed.substring(eqIdx + 1).trim();
    }
  }
  return undefined;
}

/**
 * Base64url decode (RFC 7515).
 */
function base64urlDecode(input: string): Uint8Array {
  const base64 = input.replace(/-/g, "+").replace(/_/g, "/");
  const pad = base64.length % 4;
  const padded = pad ? base64 + "=".repeat(4 - pad) : base64;
  const binary = atob(padded);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) {
    bytes[i] = binary.charCodeAt(i);
  }
  return bytes;
}

/**
 * Decode a JWT without verification (for extracting header/payload).
 */
function decodeJWT(token: string): {
  header: JWTHeader;
  payload: JWTPayload;
  signatureInput: string;
  signature: Uint8Array;
} {
  const parts = token.split(".");
  if (parts.length !== 3) {
    throw new Error("Invalid JWT: expected 3 parts");
  }

  const [headerB64, payloadB64, signatureB64] = parts as [
    string,
    string,
    string,
  ];

  const headerJson = new TextDecoder().decode(base64urlDecode(headerB64));
  const payloadJson = new TextDecoder().decode(base64urlDecode(payloadB64));

  const header = JSON.parse(headerJson) as JWTHeader;
  const payload = JSON.parse(payloadJson) as JWTPayload;
  const signature = base64urlDecode(signatureB64);
  const signatureInput = `${headerB64}.${payloadB64}`;

  return { header, payload, signatureInput, signature };
}

// ── JWKS Fetching & Caching ────────────────────────────────────────

/**
 * Fetch JWKS from Nhost, with 1-hour KV cache.
 */
async function getJWKS(
  jwksUrl: string,
  kv: KVNamespace,
): Promise<JWKSKey[]> {
  // Try cache first
  const cached = await kv.get(JWKS_CACHE_KEY);
  if (cached) {
    const parsed = JSON.parse(cached) as JWKSResponse;
    return parsed.keys;
  }

  // Fetch from Nhost
  const response = await fetch(jwksUrl);
  if (!response.ok) {
    throw new Error(`JWKS fetch failed: ${response.status} ${response.statusText}`);
  }

  const jwks = (await response.json()) as JWKSResponse;

  // Cache in KV for 1 hour
  await kv.put(JWKS_CACHE_KEY, JSON.stringify(jwks), {
    expirationTtl: JWKS_CACHE_TTL_SECONDS,
  });

  return jwks.keys;
}

/**
 * Find the matching JWK for a given kid and algorithm.
 */
function findKey(
  keys: JWKSKey[],
  kid: string | undefined,
  alg: string,
): JWKSKey | undefined {
  return keys.find(
    (k) =>
      (!kid || k.kid === kid) &&
      (!k.alg || k.alg === alg) &&
      (!k.use || k.use === "sig"),
  );
}

/**
 * Import a JWK as a CryptoKey for RS256 verification.
 */
async function importRSAKey(jwk: JWKSKey): Promise<CryptoKey> {
  return crypto.subtle.importKey(
    "jwk",
    jwk as JsonWebKey,
    { name: "RSASSA-PKCS1-v1_5", hash: "SHA-256" },
    false,
    ["verify"],
  );
}

// ── JWT Validation ─────────────────────────────────────────────────

/**
 * Validate a JWT against Nhost JWKS.
 *
 * Steps:
 *   1. Decode JWT header to get kid/alg
 *   2. Fetch JWKS (cached in KV for 1hr)
 *   3. Find matching key
 *   4. Verify signature using Web Crypto API
 *   5. Check expiration
 *   6. Extract user_id from sub claim
 */
export async function validateJWT(
  token: string,
  jwksUrl: string,
  kv: KVNamespace,
): Promise<JWTValidationResult> {
  try {
    const { header, payload, signatureInput, signature } = decodeJWT(token);

    // Only RS256 is supported (standard Nhost JWT alg)
    if (header.alg !== "RS256") {
      return { valid: false, user_id: "" };
    }

    // Fetch and find the correct key
    const keys = await getJWKS(jwksUrl, kv);
    const jwk = findKey(keys, header.kid, header.alg);
    if (!jwk) {
      return { valid: false, user_id: "" };
    }

    // Import key and verify signature
    const cryptoKey = await importRSAKey(jwk);
    const data = new TextEncoder().encode(signatureInput);
    const valid = await crypto.subtle.verify(
      "RSASSA-PKCS1-v1_5",
      cryptoKey,
      signature,
      data,
    );

    if (!valid) {
      return { valid: false, user_id: "" };
    }

    // Check expiration — exp claim is REQUIRED
    if (!payload.exp || payload.exp < Math.floor(Date.now() / 1000)) {
      return { valid: false, user_id: "" };
    }

    // Extract user_id from sub claim
    const userId = payload.sub ?? "";
    if (!userId) {
      return { valid: false, user_id: "" };
    }

    return { valid: true, user_id: userId };
  } catch {
    return { valid: false, user_id: "" };
  }
}

// ── HMAC Share Token Validation ────────────────────────────────────

/**
 * Validate an HMAC-SHA256 share token.
 *
 * Token format (generated by backend preview_service):
 *   HMAC-SHA256("{sandbox_id}:{expires_at_unix}", HMAC_SECRET).hexdigest()
 *
 * The URL contains: ?token={hex_digest}&sandbox_id={id}&expires_at={unix_ts}
 * But since sandbox_id comes from the subdomain, we only need token + expires_at.
 */
export async function validateShareToken(
  token: string,
  sandboxId: string,
  expiresAt: number,
  hmacSecret: string,
): Promise<boolean> {
  try {
    // Check expiration first (cheap check)
    const now = Math.floor(Date.now() / 1000);
    if (expiresAt <= now) {
      return false;
    }

    // Compute expected HMAC
    const message = `${sandboxId}:${expiresAt}`;
    const encoder = new TextEncoder();

    const key = await crypto.subtle.importKey(
      "raw",
      encoder.encode(hmacSecret),
      { name: "HMAC", hash: "SHA-256" },
      false,
      ["sign"],
    );

    const signatureBuffer = await crypto.subtle.sign(
      "HMAC",
      key,
      encoder.encode(message),
    );

    // Convert to hex string for comparison
    const signatureBytes = new Uint8Array(signatureBuffer);
    const expectedHex = Array.from(signatureBytes)
      .map((b) => b.toString(16).padStart(2, "0"))
      .join("");

    // Constant-time comparison to prevent timing attacks
    if (token.length !== expectedHex.length) {
      return false;
    }

    let diff = 0;
    for (let i = 0; i < token.length; i++) {
      diff |= token.charCodeAt(i) ^ expectedHex.charCodeAt(i);
    }

    return diff === 0;
  } catch {
    return false;
  }
}

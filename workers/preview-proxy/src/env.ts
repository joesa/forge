/**
 * Environment bindings for forge-preview-proxy Worker.
 *
 * All secrets come from wrangler secrets (never hardcoded).
 * KV namespace stores sandbox URL mappings.
 * Durable Object handles HMR WebSocket relay.
 */

export interface Env {
  /** Workers KV — maps "sandbox:{id}:url" → Northflank sandbox origin */
  SANDBOX_URLS: KVNamespace;

  /** Durable Object namespace — HMR relay per sandbox */
  PREVIEW_HMR: DurableObjectNamespace;

  /** HMAC secret for validating share tokens (wrangler secret) */
  HMAC_SECRET: string;

  /** Nhost JWKS endpoint URL for JWT validation */
  NHOST_JWKS_URL: string;
}

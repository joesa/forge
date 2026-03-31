"""
FORGE application configuration.

All settings loaded from environment variables via pydantic-settings.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central configuration — every value comes from an env var."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # ── App ──────────────────────────────────────────────────────────
    FORGE_ENV: str = "development"
    FORGE_SECRET_KEY: str = ""
    FORGE_ENCRYPTION_KEY: str = ""  # 32-byte base64-encoded key for AES-256-GCM
    FORGE_HMAC_SECRET: str = ""
    FORGE_FRONTEND_URL: str = "http://localhost:5173"

    # ── Database ─────────────────────────────────────────────────────
    DATABASE_URL: str = ""
    DATABASE_READ_URL: str = ""

    # ── Nhost Auth ───────────────────────────────────────────────────
    NHOST_AUTH_URL: str = ""
    NHOST_ADMIN_SECRET: str = ""

    # ── Redis (Upstash) ─────────────────────────────────────────────
    REDIS_URL: str = "redis://localhost:6379"

    # ── Cloudflare / R2 ─────────────────────────────────────────────
    CLOUDFLARE_ACCOUNT_ID: str = ""
    R2_ACCESS_KEY_ID: str = ""
    R2_SECRET_ACCESS_KEY: str = ""
    R2_BUCKET_NAME: str = "forge-projects"
    CLOUDFLARE_KV_NAMESPACE_ID: str = ""
    PREVIEW_DOMAIN: str = "preview.forge.dev"

    # ── Northflank ───────────────────────────────────────────────────
    NORTHFLANK_API_KEY: str = ""
    NORTHFLANK_PROJECT_ID: str = ""

    # ── Trigger.dev ──────────────────────────────────────────────────
    TRIGGER_API_KEY: str = ""
    TRIGGER_PROJECT_ID: str = ""

    # ── Pinecone ─────────────────────────────────────────────────────
    PINECONE_API_KEY: str = ""

    # ── AI ───────────────────────────────────────────────────────────
    ANTHROPIC_API_KEY: str = ""
    OPENAI_API_KEY: str = ""

    # ── Monitoring ───────────────────────────────────────────────────
    SENTRY_DSN: str = ""

    @property
    def is_production(self) -> bool:
        return self.FORGE_ENV == "production"


# Singleton — import this everywhere
settings = Settings()

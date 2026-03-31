"""
Tests for config.py — Settings loading.
"""

import os


def test_settings_loads_from_env():
    """Settings should pick up env vars set in conftest."""
    from app.config import settings

    assert settings.FORGE_ENV == "test"


def test_is_production_false_in_test():
    """is_production must be False when FORGE_ENV != 'production'."""
    from app.config import settings

    assert settings.is_production is False


def test_no_hardcoded_secrets():
    """No field in Settings should have a non-empty secret default.
    All secrets must come from env vars (AGENTS.md rule #8)."""
    from app.config import Settings

    # Fields that hold sensitive values
    secret_fields = [
        "FORGE_SECRET_KEY",
        "FORGE_ENCRYPTION_KEY",
        "FORGE_HMAC_SECRET",
        "NHOST_ADMIN_SECRET",
        "R2_SECRET_ACCESS_KEY",
        "NORTHFLANK_API_KEY",
        "TRIGGER_API_KEY",
        "PINECONE_API_KEY",
        "ANTHROPIC_API_KEY",
        "OPENAI_API_KEY",
        "SENTRY_DSN",
    ]

    for field_name in secret_fields:
        field_info = Settings.model_fields[field_name]
        default = field_info.default
        assert default == "", (
            f"Settings.{field_name} has non-empty default '{default}' — "
            "secrets must never be hardcoded (AGENTS.md rule #8)"
        )


def test_database_urls_are_separate():
    """Write and read database URLs must be separately configurable."""
    from app.config import settings

    # They can be the same in dev but must be distinct settings
    assert hasattr(settings, "DATABASE_URL")
    assert hasattr(settings, "DATABASE_READ_URL")

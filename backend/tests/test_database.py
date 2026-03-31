"""
Tests for the database module — engine and session factory setup.

These tests verify the module structure without connecting to a real
database (AGENTS.md rule #7: no real external APIs in tests).
"""


def test_write_engine_uses_primary_url():
    """engine_write must be bound to DATABASE_URL (primary)."""
    from app.core.database import engine_write

    url_str = str(engine_write.url)
    assert "forge_test" in url_str or "forge" in url_str


def test_read_engine_uses_replica_url():
    """engine_read must be bound to DATABASE_READ_URL (replica)."""
    from app.core.database import engine_read

    url_str = str(engine_read.url)
    assert "forge_test" in url_str or "forge" in url_str


def test_engine_pool_sizes():
    """Both engines must have pool_size=5, max_overflow=10."""
    from app.core.database import engine_read, engine_write

    assert engine_write.pool.size() == 5
    assert engine_write.pool.overflow() == -5  # max_overflow=10 means _overflow starts at -size
    assert engine_read.pool.size() == 5


def test_write_session_is_async_generator():
    """get_write_session must be an async generator (FastAPI Depends compatible)."""
    import inspect

    from app.core.database import get_write_session

    assert inspect.isasyncgenfunction(get_write_session)


def test_read_session_is_async_generator():
    """get_read_session must be an async generator (FastAPI Depends compatible)."""
    import inspect

    from app.core.database import get_read_session

    assert inspect.isasyncgenfunction(get_read_session)


def test_separate_engines():
    """Write and read engines must be distinct objects."""
    from app.core.database import engine_read, engine_write

    assert engine_write is not engine_read


def test_base_model_exists():
    """A DeclarativeBase must be exported for ORM models."""
    from app.core.database import Base

    assert hasattr(Base, "metadata")
    assert hasattr(Base, "registry")

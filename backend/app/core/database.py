"""
Async SQLAlchemy engine & session factories.

Architecture rule:
  • Writes → engine_write  (primary)   → get_write_session()
  • Reads  → engine_read   (replica)   → get_read_session()
"""

import uuid as _uuid_module
from collections.abc import AsyncGenerator

from sqlalchemy import types as sa_types
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.config import settings


# ── UUIDAsText ───────────────────────────────────────────────────────
# The Northflank PostgreSQL instance stores UUID primary/foreign keys as
# character varying (the Alembic sa.UUID() type resolved to VARCHAR here).
# Using UUID(as_uuid=True) causes asyncpg to send $1::UUID parameters,
# which PostgreSQL rejects with:
#   "operator does not exist: character varying = uuid"
# UUIDAsText keeps uuid.UUID at the Python level but binds as text,
# so comparisons are varchar = text (compatible) instead of varchar = uuid.
class UUIDAsText(sa_types.TypeDecorator):
    impl = sa_types.String
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        return str(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        if isinstance(value, _uuid_module.UUID):
            return value
        return _uuid_module.UUID(value)

# ── Engines ──────────────────────────────────────────────────────────
engine_write = create_async_engine(
    settings.DATABASE_URL,
    pool_size=5,
    max_overflow=10,
    echo=False,
)

engine_read = create_async_engine(
    settings.DATABASE_READ_URL,
    pool_size=5,
    max_overflow=10,
    echo=False,
)

# ── Session factories ───────────────────────────────────────────────
AsyncWriteSession = async_sessionmaker(
    bind=engine_write,
    class_=AsyncSession,
    expire_on_commit=False,
)

AsyncReadSession = async_sessionmaker(
    bind=engine_read,
    class_=AsyncSession,
    expire_on_commit=False,
)


# ── Base model ───────────────────────────────────────────────────────
class Base(DeclarativeBase):
    """Shared declarative base for all ORM models."""


# ── Dependency generators ────────────────────────────────────────────
async def get_write_session() -> AsyncGenerator[AsyncSession, None]:
    """Yield a session bound to the **primary** (write) database."""
    async with AsyncWriteSession() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            # Do NOT re-raise here. Route handlers that catch exceptions and
            # return a JSONResponse have already handled the error. Re-raising
            # from the dependency generator propagates through Starlette's
            # BaseHTTPMiddleware and aborts the ASGI response stream before
            # CORSMiddleware can add Access-Control headers.


async def get_read_session() -> AsyncGenerator[AsyncSession, None]:
    """Yield a session bound to the **replica** (read-only) database."""
    async with AsyncReadSession() as session:
        yield session

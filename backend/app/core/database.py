"""
Async SQLAlchemy engine & session factories.

Architecture rule:
  • Writes → engine_write  (primary)   → get_write_session()
  • Reads  → engine_read   (replica)   → get_read_session()
"""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.config import settings

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
            raise


async def get_read_session() -> AsyncGenerator[AsyncSession, None]:
    """Yield a session bound to the **replica** (read-only) database."""
    async with AsyncReadSession() as session:
        yield session

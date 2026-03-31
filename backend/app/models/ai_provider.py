"""
AIProvider model — encrypted API keys for each user's AI integrations.

Architecture rule #3: AES-256-GCM encrypted, IV stored separately.
"""

import datetime
import enum
import uuid

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ProviderName(str, enum.Enum):
    anthropic = "anthropic"
    openai = "openai"
    gemini = "gemini"
    grok = "grok"
    mistral = "mistral"
    cohere = "cohere"
    deepseek = "deepseek"
    together = "together"


class AIProvider(Base):
    __tablename__ = "ai_providers"
    __table_args__ = (
        Index(
            "uq_user_provider",
            "user_id",
            "provider_name",
            unique=True,
        ),
        Index("ix_ai_providers_user_id", "user_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("uuid_generate_v4()"),
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    provider_name: Mapped[ProviderName] = mapped_column(
        Enum(ProviderName, name="provider_name_enum", create_constraint=True),
        nullable=False,
    )
    encrypted_key: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    key_iv: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    key_tag: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)

    is_default: Mapped[bool] = mapped_column(
        Boolean, server_default=text("false"), nullable=False
    )
    is_connected: Mapped[bool] = mapped_column(
        Boolean, server_default=text("false"), nullable=False
    )
    latency_ms: Mapped[int | None] = mapped_column(Integer)

    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text("now()"),
        nullable=False,
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text("now()"),
        nullable=False,
    )

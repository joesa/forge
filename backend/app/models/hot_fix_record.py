"""
HotFixRecord model — records each auto-repair attempt by the build system.
"""

import datetime
import enum
import uuid

from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class HotFixStatus(str, enum.Enum):
    pending = "pending"
    applied = "applied"
    failed = "failed"
    reverted = "reverted"


class HotFixRecord(Base):
    __tablename__ = "hot_fix_records"
    __table_args__ = (
        Index("ix_hot_fix_records_build_id", "build_id"),
        Index("ix_hot_fix_records_project_id", "project_id"),
        Index("ix_hot_fix_records_user_id", "user_id"),
        Index("ix_hot_fix_records_user_status", "user_id", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("uuid_generate_v4()"),
    )
    build_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("builds.id", ondelete="CASCADE"),
        nullable=False,
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    status: Mapped[HotFixStatus] = mapped_column(
        Enum(HotFixStatus, name="hot_fix_status", create_constraint=True),
        server_default=text("'pending'"),
        nullable=False,
    )
    attempt_number: Mapped[int] = mapped_column(
        Integer, server_default=text("1"), nullable=False
    )
    error_input: Mapped[str | None] = mapped_column(Text)
    fix_description: Mapped[str | None] = mapped_column(Text)
    files_changed: Mapped[dict | None] = mapped_column(JSONB)

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

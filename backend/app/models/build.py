"""
Build model — represents a single build attempt with gate results.

gate_results is JSONB holding pass/fail outcomes of each quality gate.
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
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from app.core.database import UUIDAsText
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class BuildStatus(str, enum.Enum):
    pending = "pending"
    building = "building"
    succeeded = "succeeded"
    failed = "failed"


class Build(Base):
    __tablename__ = "builds"
    __table_args__ = (
        Index("ix_builds_pipeline_run_id", "pipeline_run_id"),
        Index("ix_builds_project_id", "project_id"),
        Index("ix_builds_user_id", "user_id"),
        Index("ix_builds_user_status", "user_id", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUIDAsText(),
        primary_key=True,
        server_default=text("uuid_generate_v4()"),
    )
    pipeline_run_id: Mapped[uuid.UUID] = mapped_column(
        UUIDAsText(),
        ForeignKey("pipeline_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUIDAsText(),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUIDAsText(),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    status: Mapped[BuildStatus] = mapped_column(
        Enum(BuildStatus, name="build_status", create_constraint=True),
        server_default=text("'pending'"),
        nullable=False,
    )
    build_number: Mapped[int] = mapped_column(
        Integer, server_default=text("1"), nullable=False
    )
    commit_sha: Mapped[str | None] = mapped_column(String(64))
    gate_results: Mapped[dict | None] = mapped_column(JSONB)
    log_url: Mapped[str | None] = mapped_column(String(2048))
    error_summary: Mapped[str | None] = mapped_column(Text)

    started_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True),
    )
    completed_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True),
    )

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

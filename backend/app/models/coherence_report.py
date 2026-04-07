"""
CoherenceReport model — results from the file coherence engine.

Architecture rule #5: coherence engine runs AFTER all 10 build agents.
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
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from app.core.database import UUIDAsText
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class CoherenceStatus(str, enum.Enum):
    pending = "pending"
    passed = "passed"
    failed = "failed"
    fixed = "fixed"


class CoherenceReport(Base):
    __tablename__ = "coherence_reports"
    __table_args__ = (
        Index("ix_coherence_reports_build_id", "build_id"),
        Index("ix_coherence_reports_pipeline_run_id", "pipeline_run_id"),
        Index("ix_coherence_reports_project_id", "project_id"),
        Index("ix_coherence_reports_user_id", "user_id"),
        Index("ix_coherence_reports_user_status", "user_id", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUIDAsText(),
        primary_key=True,
        server_default=text("uuid_generate_v4()"),
    )
    build_id: Mapped[uuid.UUID] = mapped_column(
        UUIDAsText(),
        ForeignKey("builds.id", ondelete="CASCADE"),
        nullable=False,
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
    status: Mapped[CoherenceStatus] = mapped_column(
        Enum(
            CoherenceStatus,
            name="coherence_status",
            create_constraint=True,
        ),
        server_default=text("'pending'"),
        nullable=False,
    )
    issues_found: Mapped[int] = mapped_column(
        Integer, server_default=text("0"), nullable=False
    )
    issues_fixed: Mapped[int] = mapped_column(
        Integer, server_default=text("0"), nullable=False
    )
    all_passed: Mapped[bool] = mapped_column(
        Boolean, server_default=text("false"), nullable=False
    )
    details: Mapped[dict | None] = mapped_column(JSONB)
    summary: Mapped[str | None] = mapped_column(Text)

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

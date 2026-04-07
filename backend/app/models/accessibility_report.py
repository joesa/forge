"""
AccessibilityReport model — WCAG 2.1 AA audit results per route.
"""

import datetime
import uuid

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from app.core.database import UUIDAsText
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class AccessibilityReport(Base):
    __tablename__ = "accessibility_reports"
    __table_args__ = (
        Index("ix_accessibility_reports_build_id", "build_id"),
        Index("ix_accessibility_reports_project_id", "project_id"),
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
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUIDAsText(),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    route: Mapped[str] = mapped_column(String(512), nullable=False)
    violations: Mapped[dict | None] = mapped_column(JSONB, server_default=text("'[]'::jsonb"))
    warnings: Mapped[dict | None] = mapped_column(JSONB, server_default=text("'[]'::jsonb"))
    passes: Mapped[int] = mapped_column(Integer, server_default=text("0"), nullable=False)
    critical_count: Mapped[int] = mapped_column(Integer, server_default=text("0"), nullable=False)
    passed_gate: Mapped[bool] = mapped_column(Boolean, server_default=text("true"), nullable=False)

    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text("now()"),
        nullable=False,
    )

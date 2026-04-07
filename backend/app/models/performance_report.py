"""
PerformanceReport model — Core Web Vitals (LCP, CLS, FID) per route.
"""

import datetime
import uuid

from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Index,
    String,
    text,
)
from app.core.database import UUIDAsText
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class PerformanceReport(Base):
    __tablename__ = "performance_reports"
    __table_args__ = (
        Index("ix_performance_reports_build_id", "build_id"),
        Index("ix_performance_reports_project_id", "project_id"),
        Index("ix_performance_reports_user_id", "user_id"),
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
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUIDAsText(),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    route: Mapped[str] = mapped_column(String(512), nullable=False)
    lcp_ms: Mapped[float | None] = mapped_column(Float)
    cls_score: Mapped[float | None] = mapped_column(Float)
    fid_ms: Mapped[float | None] = mapped_column(Float)
    ttfb_ms: Mapped[float | None] = mapped_column(Float)
    overall_score: Mapped[float | None] = mapped_column(Float)

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

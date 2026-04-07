"""
BuildSnapshot model — up to 10 snapshots per build for timeline replay.
"""

import datetime
import uuid

from sqlalchemy import (
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


class BuildSnapshot(Base):
    __tablename__ = "build_snapshots"
    __table_args__ = (
        Index("ix_build_snapshots_build_id", "build_id"),
        Index("ix_build_snapshots_project_id", "project_id"),
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
    snapshot_index: Mapped[int] = mapped_column(Integer, nullable=False)
    label: Mapped[str | None] = mapped_column(String(256))
    file_tree: Mapped[dict | None] = mapped_column(JSONB)
    screenshot_url: Mapped[str | None] = mapped_column(String(2048))

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

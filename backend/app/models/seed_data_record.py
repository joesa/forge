"""
SeedDataRecord model — tracks generated seed data for first-run experience.
"""

import datetime
import uuid

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Integer,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from app.core.database import UUIDAsText
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class SeedDataRecord(Base):
    __tablename__ = "seed_data_records"
    __table_args__ = (
        Index("ix_seed_data_records_project_id", "project_id"),
        Index("ix_seed_data_records_build_id", "build_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUIDAsText(),
        primary_key=True,
        server_default=text("uuid_generate_v4()"),
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUIDAsText(),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    build_id: Mapped[uuid.UUID | None] = mapped_column(
        UUIDAsText(),
        ForeignKey("builds.id", ondelete="SET NULL"),
    )
    tables_seeded: Mapped[dict | None] = mapped_column(JSONB, server_default=text("'[]'::jsonb"))
    total_rows: Mapped[int] = mapped_column(Integer, server_default=text("0"), nullable=False)
    seed_schema: Mapped[dict | None] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))

    applied_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text("now()"),
        nullable=False,
    )

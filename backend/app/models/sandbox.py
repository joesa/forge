"""
Sandbox model — tracks Northflank Firecracker VM instances.

Pre-warmed pool of 20+ VMs. INDEX on (status) for fast pool queries.
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
    text,
)
from app.core.database import UUIDAsText
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class SandboxStatus(str, enum.Enum):
    warming = "warming"
    ready = "ready"
    assigned = "assigned"
    terminating = "terminating"
    terminated = "terminated"


class Sandbox(Base):
    __tablename__ = "sandboxes"
    __table_args__ = (
        Index("ix_sandboxes_status", "status"),
        Index("ix_sandboxes_project_id", "project_id"),
        Index("ix_sandboxes_user_id", "user_id"),
        Index("ix_sandboxes_user_status", "user_id", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUIDAsText(),
        primary_key=True,
        server_default=text("uuid_generate_v4()"),
    )
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        UUIDAsText(),
        ForeignKey("projects.id", ondelete="SET NULL"),
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUIDAsText(),
        ForeignKey("users.id", ondelete="SET NULL"),
    )
    status: Mapped[SandboxStatus] = mapped_column(
        Enum(SandboxStatus, name="sandbox_status", create_constraint=True),
        server_default=text("'warming'"),
        nullable=False,
    )
    vm_id: Mapped[str | None] = mapped_column(String(256))
    vm_url: Mapped[str | None] = mapped_column(String(2048))
    port: Mapped[int | None] = mapped_column(Integer)

    assigned_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True),
    )
    last_heartbeat: Mapped[datetime.datetime | None] = mapped_column(
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

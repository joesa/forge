"""
Deployment model — production deployments for a project.
"""

import datetime
import enum
import uuid

from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    Index,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from app.core.database import UUIDAsText
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class DeploymentStatus(str, enum.Enum):
    pending = "pending"
    deploying = "deploying"
    live = "live"
    failed = "failed"
    rolled_back = "rolled_back"


class DeploymentTarget(str, enum.Enum):
    cloudflare_pages = "cloudflare_pages"
    northflank = "northflank"
    vercel = "vercel"


class Deployment(Base):
    __tablename__ = "deployments"
    __table_args__ = (
        Index("ix_deployments_project_id", "project_id"),
        Index("ix_deployments_build_id", "build_id"),
        Index("ix_deployments_user_id", "user_id"),
        Index("ix_deployments_user_status", "user_id", "status"),
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
    build_id: Mapped[uuid.UUID] = mapped_column(
        UUIDAsText(),
        ForeignKey("builds.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUIDAsText(),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    status: Mapped[DeploymentStatus] = mapped_column(
        Enum(
            DeploymentStatus,
            name="deployment_status",
            create_constraint=True,
        ),
        server_default=text("'pending'"),
        nullable=False,
    )
    target: Mapped[DeploymentTarget] = mapped_column(
        Enum(
            DeploymentTarget,
            name="deployment_target",
            create_constraint=True,
        ),
        nullable=False,
    )
    url: Mapped[str | None] = mapped_column(String(2048))
    commit_sha: Mapped[str | None] = mapped_column(String(64))
    deploy_log: Mapped[str | None] = mapped_column(Text)
    environment: Mapped[dict | None] = mapped_column(JSONB)

    deployed_at: Mapped[datetime.datetime | None] = mapped_column(
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

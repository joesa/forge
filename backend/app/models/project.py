"""
Project model — one row per FORGE project a user creates.
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
from app.core.database import UUIDAsText
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ProjectStatus(str, enum.Enum):
    draft = "draft"
    building = "building"
    live = "live"
    error = "error"


class ProjectFramework(str, enum.Enum):
    nextjs = "nextjs"
    react_vite = "react_vite"
    remix = "remix"
    fastapi_react = "fastapi_react"


class Project(Base):
    __tablename__ = "projects"
    __table_args__ = (
        Index(
            "ix_projects_user_status_updated",
            "user_id",
            "status",
            text("updated_at DESC"),
        ),
        Index("ix_projects_user_id", "user_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUIDAsText(),
        primary_key=True,
        server_default=text("uuid_generate_v4()"),
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUIDAsText(),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[ProjectStatus] = mapped_column(
        Enum(ProjectStatus, name="project_status", create_constraint=True),
        server_default=text("'draft'"),
        nullable=False,
    )
    framework: Mapped[ProjectFramework | None] = mapped_column(
        Enum(
            ProjectFramework,
            name="project_framework",
            create_constraint=True,
        ),
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

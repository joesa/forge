"""
EditorSession model — active editor sessions (Monaco/xterm) per project.
"""

import datetime
import uuid

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    String,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class EditorSession(Base):
    __tablename__ = "editor_sessions"
    __table_args__ = (
        Index("ix_editor_sessions_project_id", "project_id"),
        Index("ix_editor_sessions_sandbox_id", "sandbox_id"),
        Index("ix_editor_sessions_user_id", "user_id"),
        Index("ix_editor_sessions_user_status", "user_id", "is_active"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("uuid_generate_v4()"),
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
    sandbox_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("sandboxes.id", ondelete="SET NULL"),
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, server_default=text("true"), nullable=False
    )
    last_file_path: Mapped[str | None] = mapped_column(String(1024))
    open_tabs: Mapped[dict | None] = mapped_column(JSONB)

    connected_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True),
    )
    disconnected_at: Mapped[datetime.datetime | None] = mapped_column(
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

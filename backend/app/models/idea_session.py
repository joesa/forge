"""
IdeaSession model — an ideation session where a user brainstorms app ideas.
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
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class IdeaSessionStatus(str, enum.Enum):
    active = "active"
    completed = "completed"
    abandoned = "abandoned"


class IdeaSession(Base):
    __tablename__ = "idea_sessions"
    __table_args__ = (
        Index("ix_idea_sessions_user_id", "user_id"),
        Index("ix_idea_sessions_user_status", "user_id", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("uuid_generate_v4()"),
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    title: Mapped[str | None] = mapped_column(String(256))
    initial_prompt: Mapped[str | None] = mapped_column(Text)
    status: Mapped[IdeaSessionStatus] = mapped_column(
        Enum(
            IdeaSessionStatus,
            name="idea_session_status",
            create_constraint=True,
        ),
        server_default=text("'active'"),
        nullable=False,
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

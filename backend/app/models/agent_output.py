"""
AgentOutput model — stores the output of each build agent in a pipeline run.

One row per agent per pipeline run (up to 10 agents).
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
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class AgentName(str, enum.Enum):
    prd = "prd"
    design_system = "design_system"
    layout = "layout"
    component = "component"
    page = "page"
    api = "api"
    state = "state"
    integration = "integration"
    config = "config"
    quality = "quality"


class AgentOutputStatus(str, enum.Enum):
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"


class AgentOutput(Base):
    __tablename__ = "agent_outputs"
    __table_args__ = (
        Index("ix_agent_outputs_pipeline_run_id", "pipeline_run_id"),
        Index("ix_agent_outputs_user_id", "user_id"),
        Index("ix_agent_outputs_user_status", "user_id", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("uuid_generate_v4()"),
    )
    pipeline_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("pipeline_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    agent_name: Mapped[AgentName] = mapped_column(
        Enum(AgentName, name="agent_name_enum", create_constraint=True),
        nullable=False,
    )
    stage: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[AgentOutputStatus] = mapped_column(
        Enum(
            AgentOutputStatus,
            name="agent_output_status",
            create_constraint=True,
        ),
        server_default=text("'pending'"),
        nullable=False,
    )

    output_text: Mapped[str | None] = mapped_column(Text)
    output_json: Mapped[dict | None] = mapped_column(JSONB)
    token_count: Mapped[int | None] = mapped_column(Integer)
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    error_message: Mapped[str | None] = mapped_column(Text)

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

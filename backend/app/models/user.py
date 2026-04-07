"""
User model — maps to the ``users`` table.

Every row is created by Nhost Auth; we sync profile data here.
"""

import datetime
import enum
import uuid

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    Integer,
    String,
    text,
)
from app.core.database import UUIDAsText
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class PlanTier(str, enum.Enum):
    free = "free"
    pro = "pro"
    enterprise = "enterprise"


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUIDAsText(),
        primary_key=True,
        server_default=text("uuid_generate_v4()"),
    )
    email: Mapped[str] = mapped_column(
        String(320), unique=True, nullable=False
    )
    display_name: Mapped[str | None] = mapped_column(String(128))
    avatar_url: Mapped[str | None] = mapped_column(String(2048))
    onboarded: Mapped[bool] = mapped_column(
        Boolean, server_default=text("false"), nullable=False
    )
    plan: Mapped[PlanTier] = mapped_column(
        Enum(PlanTier, name="plan_tier", create_constraint=True),
        server_default=text("'free'"),
        nullable=False,
    )
    token_limit_monthly: Mapped[int] = mapped_column(
        Integer, server_default=text("100000"), nullable=False
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

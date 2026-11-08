"""A lesson plan: the teacher's scenario for one lesson.

Like ``Material``, ownership is the only authorization rule: every query is
filtered by ``owner_id`` in the service layer. Structured lesson content
(``objectives``, ``stages``) is stored as JSONB on purpose — a lesson plan is
written and read as one document; normalizing it into child tables would buy
nothing for v1 and complicate every query.
"""

import datetime
import uuid
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    Time,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from smena_api.db.base import Base, UuidPrimaryKeyMixin

if TYPE_CHECKING:  # mypy only; SQLAlchemy resolves the string via registry
    from smena_api.db.models.user import User


class LessonPlan(UuidPrimaryKeyMixin, Base):
    __tablename__ = "lesson_plans"
    __table_args__ = (
        # Empty titles never reach the database even if a future caller
        # bypasses Pydantic validation (mirrors materials).
        CheckConstraint("length(btrim(title)) > 0", name="lesson_plans_title_not_blank"),
        CheckConstraint(
            "duration_minutes IS NULL OR duration_minutes > 0",
            name="lesson_plans_duration_positive",
        ),
        Index("ix_lesson_plans_owner_updated", "owner_id", text("updated_at desc")),
        # The dashboard's "ближайший урок" block reads plans by date.
        Index("ix_lesson_plans_owner_date", "owner_id", text("lesson_date")),
    )

    owner_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    subject: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    class_name: Mapped[str] = mapped_column(String(32), nullable=False, default="")
    lesson_date: Mapped[datetime.date | None] = mapped_column(Date, nullable=True)
    start_time: Mapped[datetime.time | None] = mapped_column(Time, nullable=True)
    duration_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    topic: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    goal: Mapped[str] = mapped_column(Text, nullable=False, default="")
    # JSONB lists validated by Pydantic before they ever reach the ORM.
    objectives: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    stages: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    homework: Mapped[str] = mapped_column(Text, nullable=False, default="")
    notes: Mapped[str] = mapped_column(Text, nullable=False, default="")

    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    owner: Mapped["User"] = relationship(back_populates="lesson_plans")

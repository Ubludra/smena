"""A teacher-made assessment («проверочная»): questions with answer keys.

The questions live in their own table (ordered, cascade-deleted with the
parent) because the UI edits them one by one; each question keeps its answer
options and key as JSONB — grading models are out of v1 scope, only the
teacher authors content here. ``protected`` puts the assessment into the
«Сейф» view next to protected materials: the visibility flag is the same
grouping, never extra authorization (access stays owner-only).
"""

import datetime
import uuid
from typing import TYPE_CHECKING, Any, Literal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from smena_api.db.base import Base, UuidPrimaryKeyMixin

if TYPE_CHECKING:
    from smena_api.db.models.user import User

QUESTION_TYPES = ("single", "multi", "text")
QuestionType = Literal["single", "multi", "text"]


class Assessment(UuidPrimaryKeyMixin, Base):
    __tablename__ = "assessments"
    __table_args__ = (
        CheckConstraint("length(btrim(title)) > 0", name="assessments_title_not_blank"),
        CheckConstraint(
            "duration_minutes IS NULL OR duration_minutes > 0",
            name="assessments_duration_positive",
        ),
        Index("ix_assessments_owner_updated", "owner_id", text("updated_at desc")),
        Index("ix_assessments_owner_protected", "owner_id", text("is_protected")),
    )

    owner_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    subject: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    class_name: Mapped[str] = mapped_column(String(32), nullable=False, default="")
    scheduled_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    duration_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_protected: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    questions: Mapped[list["AssessmentQuestion"]] = relationship(
        back_populates="assessment",
        cascade="all, delete-orphan",
        passive_deletes=True,
        # Reading an assessment always needs its questions, in order.
        order_by="AssessmentQuestion.order_index",
        lazy="selectin",
    )
    owner: Mapped["User"] = relationship(back_populates="assessments")


class AssessmentQuestion(UuidPrimaryKeyMixin, Base):
    __tablename__ = "assessment_questions"
    __table_args__ = (
        CheckConstraint(
            "length(btrim(text)) > 0", name="assessment_questions_text_not_blank"
        ),
        Index(
            "ix_assessment_questions_assessment",
            "assessment_id",
            text("order_index"),
        ),
    )

    assessment_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("assessments.id", ondelete="CASCADE"), nullable=False
    )
    order_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    # "single" | "multi" | "text"
    type: Mapped[str] = mapped_column(String(16), nullable=False)
    # Choice options for single/multi; empty list for text answers.
    options: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    # Key: list[int] (indexes into options) for choice types, list[str] for
    # text (kept a list for one uniform shape).
    correct: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)

    assessment: Mapped[Assessment] = relationship(back_populates="questions")

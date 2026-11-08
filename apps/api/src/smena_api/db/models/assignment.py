"""A teacher-tracked assignment («задание»).

v1 scope: the teacher tracks what they *assigned* — class, subject, deadline,
status. There is no student model yet, so nothing pretends to receive student
submissions (no fake "24 ученика сдали"). Status is a small closed set the
teacher controls: active → done / archived.
"""

import datetime
import uuid
from typing import TYPE_CHECKING, Literal

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from smena_api.db.base import Base, UuidPrimaryKeyMixin

if TYPE_CHECKING:
    pass

# Closed status set; the DB CHECK mirrors the Pydantic Literal below.
ASSIGNMENT_STATUSES = ("active", "done", "archived")
Status = Literal["active", "done", "archived"]


class Assignment(UuidPrimaryKeyMixin, Base):
    __tablename__ = "assignments"
    __table_args__ = (
        CheckConstraint("length(btrim(title)) > 0", name="assignments_title_not_blank"),
        CheckConstraint(
            "status IN ('active', 'done', 'archived')",
            name="assignments_status_known",
        ),
        Index("ix_assignments_owner_updated", "owner_id", text("updated_at desc")),
        # Dashboard "ближайший срок / просроченные" reads by owner + due date.
        Index("ix_assignments_owner_due", "owner_id", text("due_at")),
    )

    owner_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    subject: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    class_name: Mapped[str] = mapped_column(String(32), nullable=False, default="")
    due_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active")
    # Optional link into the teacher's own library. SET NULL: deleting the
    # material must not destroy the assignment's history.
    related_material_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("materials.id", ondelete="SET NULL"), nullable=True
    )

    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

"""A report document («отчёт») written by a teacher in the Отчёты workspace.

Distinct from a teaching Material: a report is an administrative document
(self-education, class teacher, analytical certificates...). Ownership is
the only authorization rule, as everywhere: services filter by owner_id.
"""

import datetime
import uuid

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


class Report(UuidPrimaryKeyMixin, Base):
    __tablename__ = "reports"
    __table_args__ = (
        CheckConstraint("length(btrim(title)) > 0", name="reports_title_not_blank"),
        Index("ix_reports_owner_updated", "owner_id", text("updated_at desc")),
    )

    owner_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    subject: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    # Report requisites: the class the report covers and the reporting
    # period ("4 «Б»", "I четверть 2026/27" …). Free text — schools differ.
    class_name: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    period: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    content: Mapped[str] = mapped_column(Text, nullable=False, default="")

    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

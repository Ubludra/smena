"""A teacher-uploaded file («файл»).

Content lives on disk under ``settings.upload_dir``; the DB row holds only
metadata plus the *server-generated* stored name — the client never controls
the storage path, so there is no traversal surface. Downloads stream through
an owner-checked endpoint, never a static mount.

A file may optionally be attached to one of the workspace entities (material,
lesson plan, assessment, assignment, report document): an ownership-checked
link created at upload time, not a separate namespace — list/download/delete
rules stay exactly the owner-scoped ones.
"""

import datetime
import uuid
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from smena_api.db.base import Base, UuidPrimaryKeyMixin

if TYPE_CHECKING:  # mypy only; SQLAlchemy resolves the string via registry
    from smena_api.db.models.assessment import Assessment
    from smena_api.db.models.assignment import Assignment
    from smena_api.db.models.lesson_plan import LessonPlan
    from smena_api.db.models.material import Material
    from smena_api.db.models.report import Report


class UploadedFile(UuidPrimaryKeyMixin, Base):
    __tablename__ = "files"
    __table_args__ = (
        CheckConstraint(
            "length(btrim(original_name)) > 0", name="files_original_name_not_blank"
        ),
        CheckConstraint("size_bytes >= 0", name="files_size_non_negative"),
        Index("ix_files_owner_created", "owner_id", text("created_at desc")),
        Index(
            "ix_files_material",
            "material_id",
            postgresql_where=text("material_id IS NOT NULL"),
        ),
        Index(
            "ix_files_lesson_plan",
            "lesson_plan_id",
            postgresql_where=text("lesson_plan_id IS NOT NULL"),
        ),
        Index(
            "ix_files_assessment",
            "assessment_id",
            postgresql_where=text("assessment_id IS NOT NULL"),
        ),
        Index(
            "ix_files_assignment",
            "assignment_id",
            postgresql_where=text("assignment_id IS NOT NULL"),
        ),
        Index(
            "ix_files_report",
            "report_id",
            postgresql_where=text("report_id IS NOT NULL"),
        ),
    )

    owner_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    # What the teacher sees (basename only; the client never sends a path).
    original_name: Mapped[str] = mapped_column(String(255), nullable=False)
    # What the server wrote: "<uuid>.<ext>" — generated here, never from input.
    stored_name: Mapped[str] = mapped_column(String(255), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(127), nullable=False, default="")
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)

    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    # Optional attachment: a file uploaded straight from an entity's page or
    # right after creating it. SET NULL keeps the blob alive in the «Файлы»
    # drawer when the entity is deleted — a teacher never silently loses an
    # uploaded document.
    material_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("materials.id", ondelete="SET NULL"), nullable=True
    )
    lesson_plan_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("lesson_plans.id", ondelete="SET NULL"), nullable=True
    )
    assessment_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("assessments.id", ondelete="SET NULL"), nullable=True
    )
    assignment_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("assignments.id", ondelete="SET NULL"), nullable=True
    )
    report_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("reports.id", ondelete="SET NULL"), nullable=True
    )

    material: Mapped["Material | None"] = relationship()
    lesson_plan: Mapped["LessonPlan | None"] = relationship()
    assessment: Mapped["Assessment | None"] = relationship()
    assignment: Mapped["Assignment | None"] = relationship()
    report: Mapped["Report | None"] = relationship()

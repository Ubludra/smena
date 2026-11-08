"""A reusable template for creating plans, assignments, assessments, reports.

One table, four entity types: ``payload`` is a JSONB document validated —
strictly, per type — against the same Pydantic schemas the real create
endpoints use. A template can never hold content the corresponding entity
would reject: arbitrary JSON from the client is never trusted.

Rows with ``owner_id IS NULL`` are built-in system templates (the seeded
report skeletons). They are readable by everyone, mutable by nobody: the
API never lets a client create one — the ``report`` payload type exists
only as system rows, injected by the seed migration.
"""

import datetime
import uuid
from typing import TYPE_CHECKING, Any, Literal

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from smena_api.db.base import Base, UuidPrimaryKeyMixin

if TYPE_CHECKING:
    pass

TEMPLATE_ENTITY_TYPES = (
    "lesson_plan",
    "assignment",
    "assessment",
    "report",
)
TemplateEntityType = Literal["lesson_plan", "assignment", "assessment", "report"]


class Template(UuidPrimaryKeyMixin, Base):
    __tablename__ = "templates"
    __table_args__ = (
        CheckConstraint("length(btrim(name)) > 0", name="templates_name_not_blank"),
        CheckConstraint(
            "entity_type IN "
            "('lesson_plan', 'assignment', 'assessment', 'report')",
            name="templates_entity_type_known",
        ),
        Index("ix_templates_owner_updated", "owner_id", text("updated_at desc")),
    )

    # NULL = built-in system template (seeded, read-only for every user).
    owner_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(32), nullable=False)
    # Shape is guaranteed by the per-entity create schema at write time.
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)

    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    @property
    def is_system(self) -> bool:
        """Built-in template: no owner, visible to all, mutable by none."""
        return self.owner_id is None

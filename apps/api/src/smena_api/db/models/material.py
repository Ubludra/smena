"""A teaching material owned by exactly one teacher.

Ownership is the *only* authorization rule of v1: every query is filtered by
``owner_id`` in the service layer, so an object id learned by another user
grants nothing (tested as the IDOR scenario). ``is_protected`` moves the
material into the "Сейф" view; it is deliberately a visibility grouping, not
extra encryption (see docs and product spec §15).
"""

import datetime
import uuid
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from smena_api.db.base import Base, UuidPrimaryKeyMixin

if TYPE_CHECKING:  # mypy only; SQLAlchemy resolves the string via registry
    from smena_api.db.models.user import User


class Material(UuidPrimaryKeyMixin, Base):
    __tablename__ = "materials"
    __table_args__ = (
        # Empty titles never reach the database even if a future caller
        # bypasses Pydantic validation.
        CheckConstraint("length(btrim(title)) > 0", name="materials_title_not_blank"),
        Index("ix_materials_owner_updated", "owner_id", text("updated_at desc")),
    )

    owner_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    subject: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    content: Mapped[str] = mapped_column(Text, nullable=False, default="")
    is_protected: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )

    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    # "Updated" ordering drives the materials list and the dashboard's
    # "recent" block, hence the composite (owner_id, updated_at desc) index.
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    # String forward reference: SQLAlchemy resolves it via the registry at
    # mapper-configuration time; the TYPE_CHECKING import keeps mypy happy.
    owner: Mapped["User"] = relationship(back_populates="materials")

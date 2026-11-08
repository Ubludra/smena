"""Teacher account ("User" in the product spec).

Identity sources:

* production: MAX platform identity (``max_user_id`` set by the MAX launch
  verification flow — not implemented yet);
* development: ``dev-login`` derives a deterministic ``max_user_id`` of the
  form ``dev:<handle>`` so repeated logins return the same account.
"""

import datetime as dt
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from smena_api.db.base import Base, CreatedAtMixin, UuidPrimaryKeyMixin

if TYPE_CHECKING:  # mypy only; SQLAlchemy resolves the string via registry
    from smena_api.db.models.assessment import Assessment
    from smena_api.db.models.lesson_plan import LessonPlan
    from smena_api.db.models.material import Material


class User(UuidPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "users"

    # Stable platform identity. UNIQUE: two rows for the same person would
    # silently split their workspace.
    max_user_id: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(120), nullable=False)
    # scrypt hash of the Safe password set by the owner; re-typing the
    # password correctly unlocks the Safe (see api/routes/safe.py).
    # None until the Safe password is created on first unlock.
    safe_password_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)
    safe_password_version: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    safe_auth_failures: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    safe_auth_blocked_until: Mapped[dt.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # String forward reference: SQLAlchemy resolves it via the registry at
    # mapper-configuration time; the TYPE_CHECKING import keeps mypy happy.
    materials: Mapped[list["Material"]] = relationship(
        back_populates="owner", cascade="all, delete-orphan", passive_deletes=True
    )
    lesson_plans: Mapped[list["LessonPlan"]] = relationship(
        back_populates="owner", cascade="all, delete-orphan", passive_deletes=True
    )
    assessments: Mapped[list["Assessment"]] = relationship(
        back_populates="owner", cascade="all, delete-orphan", passive_deletes=True
    )

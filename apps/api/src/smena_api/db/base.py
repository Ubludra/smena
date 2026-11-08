"""Declarative base, shared mixins and column helpers."""

import datetime
import enum
import uuid

from sqlalchemy import DateTime, Enum
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.sql import func

from smena_api.core.ids import new_uuid7


class Base(DeclarativeBase):
    """Base class for all ORM models."""


class UuidPrimaryKeyMixin:
    """UUIDv7 primary key: time-ordered, unguessable (see core/ids.py)."""

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=new_uuid7)


class CreatedAtMixin:
    """Row creation timestamp (UTC, set by the database server)."""

    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


def str_enum(enum_type: type[enum.Enum]) -> Enum:
    """VARCHAR-backed enum storing the member *value* (uppercase string).

    ``native_enum=False`` avoids PostgreSQL ENUM types: they require
    ALTER TYPE for every new member and complicate migrations. A CHECK
    constraint (``create_constraint=True``) gives the same integrity with
    simpler evolution. A plain configured ``Enum`` instance is returned
    (not a subclass) so SQLAlchemy's type-adaptation machinery keeps working.
    """
    return Enum(
        enum_type,
        native_enum=False,
        length=64,
        values_callable=lambda e: [m.value for m in e],
        create_constraint=True,
    )

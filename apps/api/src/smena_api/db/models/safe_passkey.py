"""Registered Safe passkey and short-lived WebAuthn ceremonies."""

import datetime as dt
import uuid

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from smena_api.db.base import Base


class SafePasskey(Base):
    __tablename__ = "safe_passkeys"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    credential_id: Mapped[str | None] = mapped_column(
        String(1024), unique=True, nullable=True
    )
    public_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    sign_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    challenge: Mapped[str | None] = mapped_column(String(128), nullable=True)
    challenge_kind: Mapped[str | None] = mapped_column(String(16), nullable=True)
    challenge_expires: Mapped[dt.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    pending_change_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    pending_change_expires: Mapped[dt.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_request_at: Mapped[dt.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

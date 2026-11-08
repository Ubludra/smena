"""End-to-end encrypted report chat: rooms, membership, ciphertext relay.

The server is a DUMB RELAY by design (E2E guarantee):

* ``invite_hash`` stores SHA-256 of the invite token — enough to validate
  join links, useless for deriving the AES key (the client derives the key
  from the raw secret that appears only in the invite link, never in a
  request body the server stores);
* ``ciphertext`` is opaque base64 produced client-side (AES-GCM). The API
  size-checks and relays it; it never holds plaintext, keys, or read receipts.

Access rule: only members list/read/post. A non-member cannot even learn a
room exists (join without the token answers 404).
"""

import datetime
import uuid

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    PrimaryKeyConstraint,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from smena_api.db.base import Base, UuidPrimaryKeyMixin

# Relay guard: encrypted payloads are small JSON docs; anything above this
# is abuse, not a message (≈300 KB of base64).
MAX_CIPHERTEXT_CHARS = 300_000


class ReportRoom(UuidPrimaryKeyMixin, Base):
    __tablename__ = "report_rooms"
    __table_args__ = (
        CheckConstraint("length(btrim(name)) > 0", name="report_rooms_name_not_blank"),
    )

    owner_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    # sha256(invite_token) hex — join validation without storing the secret.
    invite_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)

    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class ReportRoomMember(Base):
    __tablename__ = "report_room_members"
    __table_args__ = (PrimaryKeyConstraint("room_id", "user_id"),)

    room_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("report_rooms.id", ondelete="CASCADE"), nullable=False
    )  # leading PK column — already indexed
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    joined_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class ReportMessage(UuidPrimaryKeyMixin, Base):
    __tablename__ = "report_messages"
    __table_args__ = (
        CheckConstraint(
            f"length(ciphertext) > 0 AND length(ciphertext) <= {MAX_CIPHERTEXT_CHARS}",
            name="report_messages_ciphertext_sized",
        ),
        # id is UUIDv7: time-ordered, so (room_id, id) is a stable cursor.
        Index("ix_report_messages_room_id", "room_id", "id"),
    )

    room_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("report_rooms.id", ondelete="CASCADE"), nullable=False
    )
    sender_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    ciphertext: Mapped[str] = mapped_column(Text, nullable=False)

    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

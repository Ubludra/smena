"""E2E-encrypted report chat: room lifecycle + ciphertext relay.

Every function here upholds one invariant: plaintext never exists on the
server side. The invite secret is hashed before storage (join validation);
messages are treated as opaque strings (schemas cap their size).
"""

from __future__ import annotations

import hashlib
import secrets
import uuid
from base64 import urlsafe_b64encode
from typing import TYPE_CHECKING

from sqlalchemy import exists, select

from smena_api.db.models import ReportMessage, ReportRoom, ReportRoomMember

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

_INVITE_BYTES = 24  # 32 chars b64url — plenty of entropy, well above min_length


def _hash_invite(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


async def create_room(
    session: AsyncSession, *, owner_id: uuid.UUID, name: str
) -> tuple[ReportRoom, str]:
    """Create a room; return (room, invite_token) — token shown exactly once."""
    invite_token = urlsafe_b64encode(secrets.token_bytes(_INVITE_BYTES)).decode()
    room = ReportRoom(owner_id=owner_id, name=name, invite_hash=_hash_invite(invite_token))
    session.add(room)
    await session.flush()
    session.add(ReportRoomMember(room_id=room.id, user_id=owner_id))
    await session.commit()
    await session.refresh(room)
    return room, invite_token


async def join_by_invite(
    session: AsyncSession, *, user_id: uuid.UUID, room_id: uuid.UUID, invite_token: str
) -> ReportRoom | None:
    """Validate the invite and join idempotently.

    Unknown room OR wrong token -> None (the same answer): a wrong token must
    not reveal that the room exists.
    """
    room = (
        await session.execute(
            select(ReportRoom).where(
                ReportRoom.id == room_id,
                ReportRoom.invite_hash == _hash_invite(invite_token),
            )
        )
    ).scalar_one_or_none()
    if room is None:
        return None
    already = (
        await session.execute(
            select(ReportRoomMember).where(
                ReportRoomMember.room_id == room_id,
                ReportRoomMember.user_id == user_id,
            )
        )
    ).scalar_one_or_none()
    if already is None:
        session.add(ReportRoomMember(room_id=room_id, user_id=user_id))
        await session.commit()
        await session.refresh(room)
    return room


async def list_my_rooms(
    session: AsyncSession, *, user_id: uuid.UUID
) -> list[ReportRoom]:
    rows = await session.execute(
        select(ReportRoom)
        .join(ReportRoomMember, ReportRoomMember.room_id == ReportRoom.id)
        .where(ReportRoomMember.user_id == user_id)
        .order_by(ReportRoom.created_at.desc())
    )
    return list(rows.scalars())


async def is_member(
    session: AsyncSession, *, user_id: uuid.UUID, room_id: uuid.UUID
) -> bool:
    found = (
        await session.execute(
            select(
                exists().where(
                    ReportRoomMember.room_id == room_id,
                    ReportRoomMember.user_id == user_id,
                )
            )
        )
    ).scalar_one()
    return bool(found)


async def post_message(
    session: AsyncSession, *, user_id: uuid.UUID, room_id: uuid.UUID, ciphertext: str
) -> ReportMessage:
    message = ReportMessage(room_id=room_id, sender_id=user_id, ciphertext=ciphertext)
    session.add(message)
    await session.commit()
    await session.refresh(message)
    return message


async def list_messages(
    session: AsyncSession, *, room_id: uuid.UUID, after_id: uuid.UUID | None, limit: int
) -> list[ReportMessage]:
    """Messages after an exclusive cursor id (UUIDv7 = time-ordered)."""
    conditions = [ReportMessage.room_id == room_id]
    if after_id is not None:
        conditions.append(ReportMessage.id > after_id)
    rows = await session.execute(
        select(ReportMessage)
        .where(*conditions)
        .order_by(ReportMessage.id.asc())
        .limit(limit)
    )
    return list(rows.scalars())

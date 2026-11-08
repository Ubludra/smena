"""E2E-encrypted report chat endpoints.

What the server knows: room ids/names, membership, ciphertext blobs, timing.
What it never knows: message content, titles inside shared reports, the AES
key. The invite secret only ever appears in the create response (and from
there in the invite link's hash fragment, which browsers never send).
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from smena_api.api.deps import get_current_user, get_session
from smena_api.db.models import User
from smena_api.schemas.report_chat import (
    ReportMessageCreate,
    ReportMessageOut,
    ReportRoomCreate,
    ReportRoomCreated,
    ReportRoomJoin,
    ReportRoomOut,
)
from smena_api.services import report_chat as service

router = APIRouter(prefix="/report-rooms", tags=["report-chat"])

SessionDep = Annotated[AsyncSession, Depends(get_session)]
UserDep = Annotated[User, Depends(get_current_user)]


def _not_found() -> HTTPException:
    # One answer for "no room", "wrong token", "not a member": the API never
    # confirms that a room exists to someone who shouldn't know.
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Не найдено")


@router.post("", response_model=ReportRoomCreated, status_code=status.HTTP_201_CREATED)
async def create_room(
    body: ReportRoomCreate, user: UserDep, session: SessionDep
) -> ReportRoomCreated:
    room, invite_token = await service.create_room(
        session, owner_id=user.id, name=body.name
    )
    # Hash-route link: the fragment never reaches any server, so the secret
    # travels teacher-to-teacher through the messenger, not through our logs.
    return ReportRoomCreated(
        id=room.id,
        name=room.name,
        invite_path=f"#/chat/{room.id}/{invite_token}",
        created_at=room.created_at,
    )


@router.get("", response_model=list[ReportRoomOut])
async def list_rooms(user: UserDep, session: SessionDep) -> list[ReportRoomOut]:
    rooms = await service.list_my_rooms(session, user_id=user.id)
    return [ReportRoomOut.model_validate(r) for r in rooms]


@router.post("/join", response_model=ReportRoomOut)
async def join_room(
    body: ReportRoomJoin, user: UserDep, session: SessionDep
) -> ReportRoomOut:
    room = await service.join_by_invite(
        session, user_id=user.id, room_id=body.room_id, invite_token=body.invite_token
    )
    if room is None:
        raise _not_found()
    return ReportRoomOut.model_validate(room)


@router.get("/{room_id}/messages", response_model=list[ReportMessageOut])
async def list_messages(
    room_id: uuid.UUID,
    user: UserDep,
    session: SessionDep,
    after: uuid.UUID | None = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
) -> list[ReportMessageOut]:
    if not await service.is_member(session, user_id=user.id, room_id=room_id):
        raise _not_found()
    rows = await service.list_messages(session, room_id=room_id, after_id=after, limit=limit)
    return [ReportMessageOut.model_validate(m) for m in rows]


@router.post("/{room_id}/messages", response_model=ReportMessageOut, status_code=201)
async def post_message(
    room_id: uuid.UUID,
    body: ReportMessageCreate,
    user: UserDep,
    session: SessionDep,
) -> ReportMessageOut:
    if not await service.is_member(session, user_id=user.id, room_id=room_id):
        raise _not_found()
    message = await service.post_message(
        session, user_id=user.id, room_id=room_id, ciphertext=body.ciphertext
    )
    return ReportMessageOut.model_validate(message)

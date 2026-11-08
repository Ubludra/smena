"""Schemas for the E2E-encrypted report chat.

The API only ever sees ciphertext: ``ciphertext`` is a base64 string the
client produced with WebCrypto AES-GCM. Size bounds are enforced here and
by a DB CHECK; the server never parses the payload.
"""

import uuid
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints

from smena_api.db.models.report_chat import MAX_CIPHERTEXT_CHARS

RoomName = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=200),
]
Ciphertext = Annotated[
    str, StringConstraints(min_length=1, max_length=MAX_CIPHERTEXT_CHARS)
]


class ReportRoomCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: RoomName


class ReportRoomOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    created_at: datetime


class ReportRoomCreated(BaseModel):
    """Create response: the invite secret appears ONCE, never again.

    ``invite_path`` is the client-composed hash route (``#/chat/<id>/<tok>``)
    — a hash fragment is never sent to any server, so the secret rides to the
    other participant, not into logs. The AES key itself is derived on the
    client from the same secret; the server stores only SHA-256(tok).
    """

    id: uuid.UUID
    name: str
    invite_path: str
    created_at: datetime


class ReportRoomJoin(BaseModel):
    model_config = ConfigDict(extra="forbid")

    room_id: uuid.UUID
    invite_token: Annotated[str, StringConstraints(min_length=16, max_length=128)]


class ReportMessageCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ciphertext: Ciphertext


class ReportMessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    sender_id: uuid.UUID
    ciphertext: str
    created_at: datetime

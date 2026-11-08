"""Request/response schemas for authentication."""

import uuid
from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints

# A teacher identifies themselves by name in the dev flow. The constraint
# mirrors the DB column width, rejects whitespace-only names and trims
# surrounding spaces so "Иван" and "Иван " name the same person.
DisplayName = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=120),
]


class DevLoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    display_name: DisplayName


class MaxLaunchRequest(BaseModel):
    """Body for the production MAX login.

    ``init_data`` is the raw URL-encoded string from ``WebApp.initData``
    (official MAX mini-apps contract). It is signed; the backend verifies
    the signature — never trust the client's copy of the user object.
    """

    model_config = ConfigDict(extra="forbid")

    init_data: Annotated[str, StringConstraints(min_length=1, max_length=10_000)]


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    display_name: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"  # noqa: S105  # RFC 6750 scheme name, not a credential
    user: UserOut

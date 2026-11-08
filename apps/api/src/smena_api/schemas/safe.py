"""Schemas for the Safe password unlock."""

from pydantic import BaseModel, ConfigDict, Field


class SafeStatusOut(BaseModel):
    has_password: bool
    # Deliberately no hint of any kind: a password gets no partial echo —
    # the status call is not a secret.


class SafeUnlockIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    password: str = Field(min_length=4, max_length=128)


class SafeUnlockOut(BaseModel):
    token: str
    expires_in_seconds: int

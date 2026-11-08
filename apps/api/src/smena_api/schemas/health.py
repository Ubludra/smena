"""Liveness/readiness probe schemas."""

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str


class ReadyResponse(BaseModel):
    status: str
    database: str


class NotReadyResponse(BaseModel):
    status: str
    database: str

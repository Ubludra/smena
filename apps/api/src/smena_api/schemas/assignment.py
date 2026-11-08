"""Schemas for the assignments feature.

The status is a closed Literal mirrored by a DB CHECK; ``related_material_id``
is validated against the *owner's own* library in the service layer — a
foreign material id is rejected, not silently linked.
"""

import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

Title = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=200),
]
Subject = Annotated[str, StringConstraints(strip_whitespace=True, max_length=120)]
ClassName = Annotated[str, StringConstraints(strip_whitespace=True, max_length=32)]
LongText = Annotated[str, StringConstraints(max_length=5_000)]

AssignmentStatus = Literal["active", "done", "archived"]


class AssignmentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: Title
    description: LongText = ""
    subject: Subject = ""
    class_name: ClassName = ""
    due_at: datetime | None = None
    status: AssignmentStatus = "active"
    related_material_id: uuid.UUID | None = None


class AssignmentUpdate(BaseModel):
    """Partial update: only provided fields change."""

    model_config = ConfigDict(extra="forbid")

    title: Title | None = None
    description: LongText | None = None
    subject: Subject | None = None
    class_name: ClassName | None = None
    due_at: datetime | None = None
    status: AssignmentStatus | None = None
    related_material_id: uuid.UUID | None = None


class AssignmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    description: str
    subject: str
    class_name: str
    due_at: datetime | None
    status: AssignmentStatus
    related_material_id: uuid.UUID | None
    created_at: datetime
    updated_at: datetime


class AssignmentListOut(BaseModel):
    items: list[AssignmentOut]
    total: int = Field(description="Total number of matches, ignoring pagination.")

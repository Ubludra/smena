"""Schemas for report documents (the Отчёты editor).

Same discipline as materials: validation lives here, title can never be
blank, content is bounded so one request cannot balloon the database.
"""

import uuid
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints

Title = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=200),
]
Subject = Annotated[str, StringConstraints(strip_whitespace=True, max_length=120)]
Content = Annotated[str, StringConstraints(max_length=100_000)]
ClassName = Annotated[str, StringConstraints(strip_whitespace=True, max_length=64)]
Period = Annotated[str, StringConstraints(strip_whitespace=True, max_length=120)]


class ReportDocCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: Title
    subject: Subject = ""
    class_name: ClassName = ""
    period: Period = ""
    content: Content = ""


class ReportDocUpdate(BaseModel):
    """Partial update: only provided fields change."""

    model_config = ConfigDict(extra="forbid")

    title: Title | None = None
    subject: Subject | None = None
    class_name: ClassName | None = None
    period: Period | None = None
    content: Content | None = None


class ReportDocOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    subject: str
    class_name: str
    period: str
    content: str
    created_at: datetime
    updated_at: datetime


class ReportDocListOut(BaseModel):
    items: list[ReportDocOut]
    total: int

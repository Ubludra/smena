"""Schemas for the materials feature.

Validation lives here (single place, reused by create and update); the DB
adds a last-resort CHECK on the title. Content length is bounded so a single
request cannot balloon the database — 100 000 characters is far beyond any
real lesson handout typed in a messenger webview.
"""

import uuid
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

Title = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=200),
]
Subject = Annotated[str, StringConstraints(strip_whitespace=True, max_length=120)]
Content = Annotated[str, StringConstraints(max_length=100_000)]


class MaterialCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: Title
    subject: Subject = ""
    content: Content = ""
    is_protected: bool = False


class MaterialUpdate(BaseModel):
    """Partial update: only provided fields change."""

    model_config = ConfigDict(extra="forbid")

    title: Title | None = None
    subject: Subject | None = None
    content: Content | None = None
    is_protected: bool | None = None


class MaterialOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    subject: str
    content: str
    is_protected: bool
    created_at: datetime
    updated_at: datetime


class MaterialListOut(BaseModel):
    items: list[MaterialOut]
    total: int = Field(description="Total number of matches, ignoring pagination.")

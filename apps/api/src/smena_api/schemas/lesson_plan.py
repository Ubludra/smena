"""Schemas for the lesson plans feature.

Validation lives here (single place, reused by create, update and duplicate);
the DB adds last-resort CHECKs on title and duration. ``objectives`` and
``stages`` are bounded structured JSON — the client's payload is never
trusted: every item is validated and re-serialized server-side.
"""

import uuid
from datetime import date, datetime, time
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

Title = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=200),
]
Subject = Annotated[str, StringConstraints(strip_whitespace=True, max_length=120)]
ClassName = Annotated[str, StringConstraints(strip_whitespace=True, max_length=32)]
ShortText = Annotated[str, StringConstraints(strip_whitespace=True, max_length=200)]
LongText = Annotated[str, StringConstraints(max_length=5_000)]


class StageIn(BaseModel):
    """One step of the lesson flow («ход урока»)."""

    model_config = ConfigDict(extra="forbid")

    title: Title
    minutes: Annotated[int, Field(ge=1, le=240)] | None = None
    description: LongText = ""


class LessonPlanCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: Title
    subject: Subject = ""
    class_name: ClassName = ""
    lesson_date: date | None = None
    start_time: time | None = None
    duration_minutes: Annotated[int, Field(ge=1, le=600)] | None = None
    topic: ShortText = ""
    goal: LongText = ""
    objectives: Annotated[
        list[Annotated[str, StringConstraints(max_length=500)]], Field(max_length=20)
    ] = []
    stages: Annotated[list[StageIn], Field(max_length=30)] = []
    homework: LongText = ""
    notes: LongText = ""


class LessonPlanUpdate(BaseModel):
    """Partial update: only provided fields change."""

    model_config = ConfigDict(extra="forbid")

    title: Title | None = None
    subject: Subject | None = None
    class_name: ClassName | None = None
    lesson_date: date | None = None
    start_time: time | None = None
    duration_minutes: Annotated[int, Field(ge=1, le=600)] | None = None
    topic: ShortText | None = None
    goal: LongText | None = None
    objectives: Annotated[
        list[Annotated[str, StringConstraints(max_length=500)]], Field(max_length=20)
    ] | None = None
    stages: Annotated[list[StageIn], Field(max_length=30)] | None = None
    homework: LongText | None = None
    notes: LongText | None = None


class StageOut(StageIn):
    pass


class LessonPlanOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    subject: str
    class_name: str
    lesson_date: date | None
    start_time: time | None
    duration_minutes: int | None
    topic: str
    goal: str
    objectives: list[str]
    stages: list[StageOut]
    homework: str
    notes: str
    created_at: datetime
    updated_at: datetime


class LessonPlanListOut(BaseModel):
    items: list[LessonPlanOut]
    total: int = Field(description="Total number of matches, ignoring pagination.")

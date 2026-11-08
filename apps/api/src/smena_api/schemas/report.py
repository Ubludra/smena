"""Schemas for the reports feature.

Everything here mirrors what the SQL aggregates actually computed: counts of
real owned entities over a period, Safe state, assignment deadline states and
the nearest dated items. No invented performance metrics — the data model has
no grades, so the report has none.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, Field


class ReportPeriodOut(BaseModel):
    start: datetime
    end: datetime


class CreatedCounts(BaseModel):
    materials: int
    lesson_plans: int
    assignments: int
    assessments: int


class SafeCounts(BaseModel):
    materials: int
    assessments: int


class AssignmentState(BaseModel):
    active: int = Field(description="Active assignments right now.")
    overdue: int = Field(
        description="Active assignments whose deadline has already passed."
    )
    due_soon: int = Field(
        description="Active assignments due within the next 7 days."
    )


class SubjectCount(BaseModel):
    subject: str
    count: int


class UpcomingItem(BaseModel):
    type: Literal["lesson_plan", "assignment"]
    id: uuid.UUID
    title: str
    date: datetime


class ReportOut(BaseModel):
    period: ReportPeriodOut
    created: CreatedCounts
    safe: SafeCounts
    assignments: AssignmentState
    materials_by_subject: Annotated[
        list[SubjectCount], Field(max_length=5, description="Top subjects, descending.")
    ]
    upcoming: Annotated[
        list[UpcomingItem], Field(max_length=5, description="Nearest dated items.")
    ]

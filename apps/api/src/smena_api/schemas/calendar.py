"""Schemas for the calendar view (read-only aggregation)."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, ConfigDict


class CalendarEvent(BaseModel):
    """One dot on the month grid. ``date`` is a plain calendar date (no tz) —
    the grid is drawn in the teacher's day, not in an instant of time."""

    model_config = ConfigDict(from_attributes=True)

    type: str  # "lesson_plan" | "assignment" | "assessment"
    id: str
    title: str
    date: date
    time: str | None = None  # "HH:MM" when the source carries a time
    status: str | None = None  # assignments carry active/done/archived


class CalendarOut(BaseModel):
    year: int
    month: int
    events: list[CalendarEvent]

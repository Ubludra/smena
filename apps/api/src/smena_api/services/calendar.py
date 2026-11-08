"""Calendar aggregation: one month, three sources, owner-scoped.

Read-only view over existing tables — no new storage. Each row contributes
one event on the calendar day its own date field points at:

* LessonPlan → ``lesson_date`` (+ ``start_time`` as the optional clock time);
* Assignment → ``due_at`` (active only: done/archived are history, not plans);
* Assessment → ``scheduled_at``.
"""

from __future__ import annotations

import datetime as dt
import uuid
from typing import TYPE_CHECKING

from sqlalchemy import select

from smena_api.db.models import Assessment, Assignment, LessonPlan
from smena_api.schemas.calendar import CalendarEvent, CalendarOut

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

_LAST_DAY = (31, 29, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)


def month_bounds(year: int, month: int) -> tuple[dt.date, dt.date]:
    """First day of the month and the last day of it."""
    last = _LAST_DAY[month - 1]
    if month == 2 and not (year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)):
        last = 28
    return dt.date(year, month, 1), dt.date(year, month, last)


def validate_month(year: int, month: int) -> bool:
    return 2000 <= year <= 2100 and 1 <= month <= 12


def current_month() -> tuple[int, int]:
    return dt.datetime.now(tz=dt.UTC).date().year, dt.datetime.now(tz=dt.UTC).date().month


def _tz_day_window(day: dt.date) -> tuple[dt.datetime, dt.datetime]:
    start = dt.datetime.combine(day, dt.time.min, tzinfo=dt.UTC)
    end = dt.datetime.combine(day, dt.time.max, tzinfo=dt.UTC)
    return start, end


async def month_events(
    session: AsyncSession,
    *,
    owner_id: uuid.UUID,
    year: int,
    month: int,
) -> CalendarOut:
    """Events of one month, ordered by date then time."""
    start, end = month_bounds(year, month)
    window_start = _tz_day_window(start)[0]
    window_end = _tz_day_window(end)[1]

    plans = await session.execute(
        select(LessonPlan).where(
            LessonPlan.owner_id == owner_id,
            LessonPlan.lesson_date.is_not(None),
            LessonPlan.lesson_date >= start,
            LessonPlan.lesson_date <= end,
        )
    )
    assignments = await session.execute(
        select(Assignment).where(
            Assignment.owner_id == owner_id,
            Assignment.status == "active",
            Assignment.due_at.is_not(None),
            Assignment.due_at >= window_start,
            Assignment.due_at <= window_end,
        )
    )
    assessments = await session.execute(
        select(Assessment).where(
            Assessment.owner_id == owner_id,
            Assessment.scheduled_at.is_not(None),
            Assessment.scheduled_at >= window_start,
            Assessment.scheduled_at <= window_end,
        )
    )

    events: list[CalendarEvent] = []
    for plan in plans.scalars():
        if plan.lesson_date is None:
            continue
        events.append(
            CalendarEvent(
                type="lesson_plan",
                id=str(plan.id),
                title=plan.title,
                date=plan.lesson_date,
                time=plan.start_time.strftime("%H:%M") if plan.start_time else None,
            )
        )
    for assignment in assignments.scalars():
        if assignment.due_at is None:
            continue
        utc = assignment.due_at.astimezone(dt.UTC)
        events.append(
            CalendarEvent(
                type="assignment",
                id=str(assignment.id),
                title=assignment.title,
                date=utc.date(),
                time=utc.strftime("%H:%M"),
                status=assignment.status,
            )
        )
    for assessment in assessments.scalars():
        if assessment.scheduled_at is None:
            continue
        utc = assessment.scheduled_at.astimezone(dt.UTC)
        events.append(
            CalendarEvent(
                type="assessment",
                id=str(assessment.id),
                title=assessment.title,
                date=utc.date(),
                time=utc.strftime("%H:%M"),
            )
        )

    events.sort(key=lambda e: (e.date, e.time or ""))
    return CalendarOut(year=year, month=month, events=events)

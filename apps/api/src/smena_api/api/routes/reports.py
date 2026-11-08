"""Reports: real aggregates over the teacher's own data.

Nothing here is invented: every number is a SQL count/group over entities the
teacher actually owns. Student performance, grades and attendance do not
exist in the data model, so they do not exist in the reports. Ownership is
enforced in every query below — the acting user comes from the verified
token, and aggregation never mixes teachers.
"""

from __future__ import annotations

import datetime as dt
import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from smena_api.api.deps import get_current_user, get_session
from smena_api.db.models import Assessment, Assignment, LessonPlan, Material, User
from smena_api.schemas.report import (
    AssignmentState,
    CreatedCounts,
    ReportOut,
    ReportPeriodOut,
    SafeCounts,
    SubjectCount,
    UpcomingItem,
)

router = APIRouter(prefix="/reports", tags=["reports"])

SessionDep = Annotated[AsyncSession, Depends(get_session)]
UserDep = Annotated[User, Depends(get_current_user)]

Period = Literal["7d", "30d", "month", "custom"]


def _resolve_period(
    period: str,
    date_from: dt.date | None,
    date_to: dt.date | None,
) -> tuple[dt.datetime, dt.datetime]:
    """Reporting window [from, to] in UTC from the requested period."""
    now = dt.datetime.now(dt.UTC)
    today = now.date()
    if period == "7d":
        return now - dt.timedelta(days=7), now
    if period == "30d":
        return now - dt.timedelta(days=30), now
    if period == "month":
        month_start = dt.datetime(today.year, today.month, 1, tzinfo=dt.UTC)
        return month_start, now
    # custom
    if date_from is None or date_to is None:
        raise _bad_period("Для произвольного периода нужны date_from и date_to")
    if date_from > date_to:
        raise _bad_period("date_from не может быть позже date_to")
    return (
        dt.datetime(
            date_from.year, date_from.month, date_from.day, tzinfo=dt.UTC
        ),
        dt.datetime(
            date_to.year,
            date_to.month,
            date_to.day,
            23,
            59,
            59,
            tzinfo=dt.UTC,
        ),
    )


def _bad_period(message: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail=message,
    )


async def _count_created(
    # The four audited models share owner_id/created_at; a narrow union keeps
    # mypy happy without a protocol dance for a private helper.
    session: AsyncSession,
    model: type[Material] | type[Assignment] | type[LessonPlan] | type[Assessment],
    owner_id: uuid.UUID,
    window_start: dt.datetime,
) -> int:
    row = await session.execute(
        select(func.count())
        .select_from(model)
        .where(model.owner_id == owner_id, model.created_at >= window_start)
    )
    return int(row.scalar_one())


@router.get("/summary", response_model=ReportOut)
async def report_summary(
    user: UserDep,
    session: SessionDep,
    period: Period = "30d",
    date_from: dt.date | None = None,
    date_to: dt.date | None = None,
) -> ReportOut:
    window_start, window_end = _resolve_period(period, date_from, date_to)
    owner_id = user.id
    now = dt.datetime.now(dt.UTC)
    today = now.date()
    week_ahead = now + dt.timedelta(days=7)

    created_materials = await _count_created(session, Material, owner_id, window_start)
    created_plans = await _count_created(session, LessonPlan, owner_id, window_start)
    created_assignments = await _count_created(session, Assignment, owner_id, window_start)
    created_assessments = await _count_created(session, Assessment, owner_id, window_start)

    # Safe contents: a present-state count, not a period one.
    safe_materials = int(
        (
            await session.execute(
                select(func.count())
                .select_from(Material)
                .where(Material.owner_id == owner_id, Material.is_protected.is_(True))
            )
        ).scalar_one()
    )
    safe_assessments = int(
        (
            await session.execute(
                select(func.count())
                .select_from(Assessment)
                .where(Assessment.owner_id == owner_id, Assessment.is_protected.is_(True))
            )
        ).scalar_one()
    )

    # Assignment states are computed in SQL from real deadlines.
    assignment_rows = await session.execute(
        select(
            func.count().filter(Assignment.status == "active").label("active"),
            func.count()
            .filter(
                Assignment.status == "active",
                Assignment.due_at.is_not(None),
                Assignment.due_at < now,
            )
            .label("overdue"),
            func.count()
            .filter(
                Assignment.status == "active",
                Assignment.due_at >= now,
                Assignment.due_at < week_ahead,
            )
            .label("due_soon"),
        ).where(Assignment.owner_id == owner_id)
    )
    assignments_state = assignment_rows.one()

    # Materials by subject (top 5), only non-empty subjects.
    subject_rows = await session.execute(
        select(Material.subject, func.count().label("total"))
        .where(
            Material.owner_id == owner_id,
            func.btrim(Material.subject) != "",
        )
        .group_by(Material.subject)
        .order_by(func.count().desc())
        .limit(5)
    )
    materials_by_subject = [
        SubjectCount(subject=row.subject, count=int(row.total)) for row in subject_rows
    ]

    # Nearest dated plans + active assignment deadlines, merged by date.
    plan_rows = await session.execute(
        select(LessonPlan)
        .where(
            LessonPlan.owner_id == owner_id,
            LessonPlan.lesson_date.is_not(None),
            LessonPlan.lesson_date >= today,
        )
        .order_by(LessonPlan.lesson_date.asc(), LessonPlan.start_time.asc().nulls_last())
        .limit(5)
    )
    upcoming: list[UpcomingItem] = []
    for plan in plan_rows.scalars():
        lesson_date = plan.lesson_date
        if lesson_date is None:  # pragma: no cover — filtered in SQL above
            continue
        upcoming.append(
            UpcomingItem(
                type="lesson_plan",
                id=plan.id,
                title=plan.title,
                date=dt.datetime(
                    lesson_date.year,
                    lesson_date.month,
                    lesson_date.day,
                    tzinfo=dt.UTC,
                ),
            )
        )
    assignment_deadlines = await session.execute(
        select(Assignment)
        .where(
            Assignment.owner_id == owner_id,
            Assignment.status == "active",
            Assignment.due_at.is_not(None),
            Assignment.due_at >= now,
        )
        .order_by(Assignment.due_at.asc())
        .limit(5)
    )
    upcoming.extend(
        UpcomingItem(
            type="assignment",
            id=assignment.id,
            title=assignment.title,
            date=assignment.due_at,
        )
        for assignment in assignment_deadlines.scalars()
        if assignment.due_at is not None  # pragma: no cover — filtered in SQL
    )
    upcoming.sort(key=lambda item: item.date)
    upcoming = upcoming[:5]

    return ReportOut(
        period=ReportPeriodOut(start=window_start, end=window_end),
        created=CreatedCounts(
            materials=created_materials,
            lesson_plans=created_plans,
            assignments=created_assignments,
            assessments=created_assessments,
        ),
        safe=SafeCounts(materials=safe_materials, assessments=safe_assessments),
        assignments=AssignmentState(
            active=int(assignments_state.active),
            overdue=int(assignments_state.overdue),
            due_soon=int(assignments_state.due_soon),
        ),
        materials_by_subject=materials_by_subject,
        upcoming=upcoming,
    )

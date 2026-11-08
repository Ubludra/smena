"""Lesson plans business logic.

Same ownership discipline as materials: this service is the *only* place that
composes owner-filtered queries; every function takes ``owner_id`` and filters
by it. Routes never build queries.
"""

from __future__ import annotations

import datetime
import uuid
from typing import TYPE_CHECKING, Any

from sqlalchemy import func, or_, select

from smena_api.db.models import LessonPlan
from smena_api.schemas.lesson_plan import LessonPlanCreate, LessonPlanUpdate

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

# «Копия» suffix must survive the 200-char title limit.
_DUPLICATE_SUFFIX = " (копия)"


async def list_lesson_plans(
    session: AsyncSession,
    *,
    owner_id: uuid.UUID,
    search: str = "",
    class_name: str = "",
    subject: str = "",
    date_from: datetime.date | None = None,
    date_to: datetime.date | None = None,
    limit: int = 20,
    offset: int = 0,
) -> tuple[list[LessonPlan], int]:
    """Owner's plans, newest-modified first, with optional filtering."""
    conditions: list[Any] = [LessonPlan.owner_id == owner_id]
    needle = search.strip()
    if needle:
        pattern = f"%{needle}%"
        conditions.append(or_(LessonPlan.title.ilike(pattern), LessonPlan.topic.ilike(pattern)))
    class_needle = class_name.strip()
    if class_needle:
        conditions.append(LessonPlan.class_name.ilike(f"%{class_needle}%"))
    subject_needle = subject.strip()
    if subject_needle:
        conditions.append(LessonPlan.subject.ilike(f"%{subject_needle}%"))
    if date_from is not None:
        conditions.append(LessonPlan.lesson_date >= date_from)
    if date_to is not None:
        conditions.append(LessonPlan.lesson_date <= date_to)

    total = (
        await session.execute(select(func.count()).select_from(LessonPlan).where(*conditions))
    ).scalar_one()
    rows = await session.execute(
        select(LessonPlan)
        .where(*conditions)
        .order_by(LessonPlan.updated_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(rows.scalars()), int(total)


async def list_upcoming(
    session: AsyncSession,
    *,
    owner_id: uuid.UUID,
    today: datetime.date,
    limit: int = 3,
) -> list[LessonPlan]:
    """Nearest dated plans from ``today`` onward (for the dashboard).

    Undated plans are drafts by definition — they never appear here.
    """
    rows = await session.execute(
        select(LessonPlan)
        .where(
            LessonPlan.owner_id == owner_id,
            LessonPlan.lesson_date.is_not(None),
            LessonPlan.lesson_date >= today,
        )
        .order_by(LessonPlan.lesson_date.asc(), LessonPlan.start_time.asc().nulls_last())
        .limit(limit)
    )
    return list(rows.scalars())


async def get_owned(
    session: AsyncSession, *, owner_id: uuid.UUID, lesson_plan_id: uuid.UUID
) -> LessonPlan | None:
    """Return the plan only if it belongs to ``owner_id``; else None.

    None for both "missing" and "foreign" — the route maps both to 404 so the
    API never confirms that a foreign id exists (no existence oracle).
    """
    row = await session.execute(
        select(LessonPlan).where(
            LessonPlan.id == lesson_plan_id, LessonPlan.owner_id == owner_id
        )
    )
    return row.scalar_one_or_none()


async def create(
    session: AsyncSession, *, owner_id: uuid.UUID, data: LessonPlanCreate
) -> LessonPlan:
    plan = LessonPlan(owner_id=owner_id, **data.model_dump())
    session.add(plan)
    await session.commit()
    await session.refresh(plan)
    return plan


async def update(
    session: AsyncSession, plan: LessonPlan, data: LessonPlanUpdate
) -> LessonPlan:
    changes = data.model_dump(exclude_unset=True)
    for field, value in changes.items():
        setattr(plan, field, value)
    await session.commit()
    await session.refresh(plan)
    return plan


async def duplicate(session: AsyncSession, plan: LessonPlan) -> LessonPlan:
    """Copy the plan as a new row owned by the same teacher."""
    base_title = plan.title.removesuffix(_DUPLICATE_SUFFIX)
    max_base = 200 - len(_DUPLICATE_SUFFIX)
    copy = LessonPlan(
        owner_id=plan.owner_id,
        title=f"{base_title[:max_base].rstrip()}{_DUPLICATE_SUFFIX}",
        subject=plan.subject,
        class_name=plan.class_name,
        lesson_date=plan.lesson_date,
        start_time=plan.start_time,
        duration_minutes=plan.duration_minutes,
        topic=plan.topic,
        goal=plan.goal,
        # Deep copies: JSONB columns are shared references until reassigned.
        objectives=list(plan.objectives),
        stages=[dict(stage) for stage in plan.stages],
        homework=plan.homework,
        notes=plan.notes,
    )
    session.add(copy)
    await session.commit()
    await session.refresh(copy)
    return copy


async def delete(session: AsyncSession, plan: LessonPlan) -> None:
    await session.delete(plan)
    await session.commit()

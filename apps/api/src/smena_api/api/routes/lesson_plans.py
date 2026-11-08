"""Lesson plans endpoints.

Same authorization model as materials: the acting user comes from the
verified token; every query is owner-scoped in the service layer. Foreign or
missing ids both answer 404 — the API never confirms the existence of someone
else's plan.
"""

import datetime
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from smena_api.api.deps import get_current_user, get_session
from smena_api.db.models import User
from smena_api.schemas.lesson_plan import (
    LessonPlanCreate,
    LessonPlanListOut,
    LessonPlanOut,
    LessonPlanUpdate,
)
from smena_api.services import lesson_plans as service

router = APIRouter(prefix="/lesson-plans", tags=["lesson-plans"])

SessionDep = Annotated[AsyncSession, Depends(get_session)]
UserDep = Annotated[User, Depends(get_current_user)]


@router.get("", response_model=LessonPlanListOut)
async def list_lesson_plans(
    user: UserDep,
    session: SessionDep,
    search: Annotated[str, Query(max_length=200)] = "",
    class_name: Annotated[str, Query(max_length=32)] = "",
    subject: Annotated[str, Query(max_length=120)] = "",
    date_from: datetime.date | None = None,
    date_to: datetime.date | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> LessonPlanListOut:
    items, total = await service.list_lesson_plans(
        session,
        owner_id=user.id,
        search=search,
        class_name=class_name,
        subject=subject,
        date_from=date_from,
        date_to=date_to,
        limit=limit,
        offset=offset,
    )
    return LessonPlanListOut(
        items=[LessonPlanOut.model_validate(p) for p in items],
        total=total,
    )


@router.post("", response_model=LessonPlanOut, status_code=status.HTTP_201_CREATED)
async def create_lesson_plan(
    body: LessonPlanCreate, user: UserDep, session: SessionDep
) -> LessonPlanOut:
    plan = await service.create(session, owner_id=user.id, data=body)
    return LessonPlanOut.model_validate(plan)


@router.get("/{plan_id}", response_model=LessonPlanOut)
async def get_lesson_plan(plan_id: uuid.UUID, user: UserDep, session: SessionDep) -> LessonPlanOut:
    plan = await service.get_owned(session, owner_id=user.id, lesson_plan_id=plan_id)
    if plan is None:
        raise _not_found()
    return LessonPlanOut.model_validate(plan)


@router.patch("/{plan_id}", response_model=LessonPlanOut)
async def update_lesson_plan(
    plan_id: uuid.UUID, body: LessonPlanUpdate, user: UserDep, session: SessionDep
) -> LessonPlanOut:
    plan = await service.get_owned(session, owner_id=user.id, lesson_plan_id=plan_id)
    if plan is None:
        raise _not_found()
    plan = await service.update(session, plan, body)
    return LessonPlanOut.model_validate(plan)


@router.post(
    "/{plan_id}/duplicate",
    response_model=LessonPlanOut,
    status_code=status.HTTP_201_CREATED,
)
async def duplicate_lesson_plan(
    plan_id: uuid.UUID, user: UserDep, session: SessionDep
) -> LessonPlanOut:
    plan = await service.get_owned(session, owner_id=user.id, lesson_plan_id=plan_id)
    if plan is None:
        raise _not_found()
    copy = await service.duplicate(session, plan)
    return LessonPlanOut.model_validate(copy)


@router.delete("/{plan_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_lesson_plan(plan_id: uuid.UUID, user: UserDep, session: SessionDep) -> None:
    plan = await service.get_owned(session, owner_id=user.id, lesson_plan_id=plan_id)
    if plan is None:
        raise _not_found()
    await service.delete(session, plan)


def _not_found() -> HTTPException:
    # Same message/code for "missing" and "foreign": no existence oracle.
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="План урока не найден",
    )

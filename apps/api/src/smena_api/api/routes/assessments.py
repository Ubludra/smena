"""Assessments endpoints («Проверочные»).

Same authorization model as the other modules: the acting user comes from
the verified token; every query is owner-scoped in the service layer. Foreign
or missing ids both answer 404 — the API never confirms the existence of
someone else's assessment.
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from smena_api.api.deps import get_current_user, get_session
from smena_api.api.routes.safe import require_safe_unlock
from smena_api.db.models import User
from smena_api.schemas.assessment import (
    AssessmentCreate,
    AssessmentListOut,
    AssessmentOut,
    AssessmentUpdate,
)
from smena_api.services import assessments as service

router = APIRouter(prefix="/assessments", tags=["assessments"])

SessionDep = Annotated[AsyncSession, Depends(get_session)]
UserDep = Annotated[User, Depends(get_current_user)]


@router.get("", response_model=AssessmentListOut)
async def list_assessments(
    request: Request,
    user: UserDep,
    session: SessionDep,
    search: Annotated[str, Query(max_length=200)] = "",
    class_name: Annotated[str, Query(max_length=32)] = "",
    subject: Annotated[str, Query(max_length=120)] = "",
    only_protected: bool = False,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> AssessmentListOut:
    if only_protected:
        # The Safe view is gated by the phone unlock (see api/routes/safe.py).
        require_safe_unlock(request, user)
    items, total = await service.list_assessments(
        session,
        owner_id=user.id,
        search=search,
        class_name=class_name,
        subject=subject,
        only_protected=only_protected,
        limit=limit,
        offset=offset,
    )
    return AssessmentListOut(
        items=[AssessmentOut.model_validate(a) for a in items],
        total=total,
    )


@router.post("", response_model=AssessmentOut, status_code=status.HTTP_201_CREATED)
async def create_assessment(
    body: AssessmentCreate, user: UserDep, session: SessionDep
) -> AssessmentOut:
    assessment = await service.create(session, owner_id=user.id, data=body)
    return AssessmentOut.model_validate(assessment)


@router.get("/{assessment_id}", response_model=AssessmentOut)
async def get_assessment(
    assessment_id: uuid.UUID, request: Request, user: UserDep, session: SessionDep
) -> AssessmentOut:
    assessment = await service.get_owned(
        session, owner_id=user.id, assessment_id=assessment_id
    )
    if assessment is None:
        raise _not_found()
    if assessment.is_protected:
        # Protected content only opens after the Safe unlock (see safe.py).
        require_safe_unlock(request, user)
    return AssessmentOut.model_validate(assessment)


@router.patch("/{assessment_id}", response_model=AssessmentOut)
async def update_assessment(
    assessment_id: uuid.UUID,
    body: AssessmentUpdate,
    user: UserDep,
    session: SessionDep,
) -> AssessmentOut:
    assessment = await service.get_owned(
        session, owner_id=user.id, assessment_id=assessment_id
    )
    if assessment is None:
        raise _not_found()
    assessment = await service.update(session, assessment, body)
    return AssessmentOut.model_validate(assessment)


@router.post(
    "/{assessment_id}/duplicate",
    response_model=AssessmentOut,
    status_code=status.HTTP_201_CREATED,
)
async def duplicate_assessment(
    assessment_id: uuid.UUID, user: UserDep, session: SessionDep
) -> AssessmentOut:
    """Copy an owned assessment with its questions (a justified verb route)."""
    assessment = await service.get_owned(
        session, owner_id=user.id, assessment_id=assessment_id
    )
    if assessment is None:
        raise _not_found()
    copy = await service.duplicate(session, assessment)
    return AssessmentOut.model_validate(copy)


@router.delete("/{assessment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_assessment(
    assessment_id: uuid.UUID, user: UserDep, session: SessionDep
) -> None:
    assessment = await service.get_owned(
        session, owner_id=user.id, assessment_id=assessment_id
    )
    if assessment is None:
        raise _not_found()
    await service.delete(session, assessment)


def _not_found() -> HTTPException:
    # Same message/code for "missing" and "foreign": no existence oracle.
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Проверочная не найдена",
    )

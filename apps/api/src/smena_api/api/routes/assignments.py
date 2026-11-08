"""Assignments endpoints.

Same authorization model as materials and lesson plans: the acting user comes
from the verified token; every query is owner-scoped in the service layer.
Foreign or missing ids both answer 404 — the API never confirms the existence
of someone else's assignment.
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from smena_api.api.deps import get_current_user, get_session
from smena_api.db.models import User
from smena_api.schemas.assignment import (
    AssignmentCreate,
    AssignmentListOut,
    AssignmentOut,
    AssignmentUpdate,
)
from smena_api.services import assignments as service

router = APIRouter(prefix="/assignments", tags=["assignments"])

SessionDep = Annotated[AsyncSession, Depends(get_session)]
UserDep = Annotated[User, Depends(get_current_user)]


@router.get("", response_model=AssignmentListOut)
async def list_assignments(
    user: UserDep,
    session: SessionDep,
    search: Annotated[str, Query(max_length=200)] = "",
    status_filter: Annotated[str, Query(alias="status", max_length=16)] = "",
    class_name: Annotated[str, Query(max_length=32)] = "",
    subject: Annotated[str, Query(max_length=120)] = "",
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> AssignmentListOut:
    items, total = await service.list_assignments(
        session,
        owner_id=user.id,
        search=search,
        status=status_filter,
        class_name=class_name,
        subject=subject,
        limit=limit,
        offset=offset,
    )
    return AssignmentListOut(
        items=[AssignmentOut.model_validate(a) for a in items],
        total=total,
    )


@router.post("", response_model=AssignmentOut, status_code=status.HTTP_201_CREATED)
async def create_assignment(
    body: AssignmentCreate, user: UserDep, session: SessionDep
) -> AssignmentOut:
    try:
        assignment = await service.create(session, owner_id=user.id, data=body)
    except service.RelatedMaterialError:
        raise _bad_related_material() from None
    return AssignmentOut.model_validate(assignment)


@router.get("/{assignment_id}", response_model=AssignmentOut)
async def get_assignment(
    assignment_id: uuid.UUID, user: UserDep, session: SessionDep
) -> AssignmentOut:
    assignment = await service.get_owned(
        session, owner_id=user.id, assignment_id=assignment_id
    )
    if assignment is None:
        raise _not_found()
    return AssignmentOut.model_validate(assignment)


@router.patch("/{assignment_id}", response_model=AssignmentOut)
async def update_assignment(
    assignment_id: uuid.UUID,
    body: AssignmentUpdate,
    user: UserDep,
    session: SessionDep,
) -> AssignmentOut:
    assignment = await service.get_owned(
        session, owner_id=user.id, assignment_id=assignment_id
    )
    if assignment is None:
        raise _not_found()
    try:
        assignment = await service.update(session, assignment, body)
    except service.RelatedMaterialError:
        raise _bad_related_material() from None
    return AssignmentOut.model_validate(assignment)


@router.delete("/{assignment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_assignment(
    assignment_id: uuid.UUID, user: UserDep, session: SessionDep
) -> None:
    assignment = await service.get_owned(
        session, owner_id=user.id, assignment_id=assignment_id
    )
    if assignment is None:
        raise _not_found()
    await service.delete(session, assignment)


def _not_found() -> HTTPException:
    # Same message/code for "missing" and "foreign": no existence oracle.
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Задание не найдено",
    )


def _bad_related_material() -> HTTPException:
    # 422, not 404: the problem is the request body (linking someone else's
    # material), not a resource address.
    return HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail="Связанный материал не найден в вашей библиотеке",
    )

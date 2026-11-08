"""Report documents endpoints (the Отчёты editor).

Ownership discipline as everywhere: token user scopes every query; foreign
and missing ids both answer 404.
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from smena_api.api.deps import get_current_user, get_session
from smena_api.db.models import User
from smena_api.schemas.report_doc import (
    ReportDocCreate,
    ReportDocListOut,
    ReportDocOut,
    ReportDocUpdate,
)
from smena_api.services import report_docs as service

router = APIRouter(prefix="/reports", tags=["reports"])

SessionDep = Annotated[AsyncSession, Depends(get_session)]
UserDep = Annotated[User, Depends(get_current_user)]


def _not_found() -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Не найдено")


@router.get("", response_model=ReportDocListOut)
async def list_reports(
    user: UserDep,
    session: SessionDep,
    search: Annotated[str, Query(max_length=200)] = "",
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> ReportDocListOut:
    items, total = await service.list_reports(
        session, owner_id=user.id, search=search, limit=limit, offset=offset
    )
    return ReportDocListOut(
        items=[ReportDocOut.model_validate(r) for r in items], total=total
    )


@router.post("", response_model=ReportDocOut, status_code=status.HTTP_201_CREATED)
async def create_report(
    body: ReportDocCreate, user: UserDep, session: SessionDep
) -> ReportDocOut:
    report = await service.create(session, owner_id=user.id, data=body)
    return ReportDocOut.model_validate(report)


# NOTE: defined before "/{report_id}" (in module order across routers the
# summary route registers first) so "/reports/summary" is never parsed as an
# id. This router itself has no other static subpaths.
@router.get("/{report_id}", response_model=ReportDocOut)
async def get_report(
    report_id: uuid.UUID, user: UserDep, session: SessionDep
) -> ReportDocOut:
    report = await service.get_owned(session, owner_id=user.id, report_id=report_id)
    if report is None:
        raise _not_found()
    return ReportDocOut.model_validate(report)


@router.patch("/{report_id}", response_model=ReportDocOut)
async def update_report(
    report_id: uuid.UUID, body: ReportDocUpdate, user: UserDep, session: SessionDep
) -> ReportDocOut:
    report = await service.get_owned(session, owner_id=user.id, report_id=report_id)
    if report is None:
        raise _not_found()
    return ReportDocOut.model_validate(
        await service.update(session, report=report, data=body)
    )


@router.delete("/{report_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_report(
    report_id: uuid.UUID, user: UserDep, session: SessionDep
) -> None:
    report = await service.get_owned(session, owner_id=user.id, report_id=report_id)
    if report is None:
        raise _not_found()
    await service.delete(session, report=report)

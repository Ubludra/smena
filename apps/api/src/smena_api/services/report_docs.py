"""Report documents business logic — ownership-scoped CRUD, no more."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

from sqlalchemy import func, select

from smena_api.db.models import Report
from smena_api.schemas.report_doc import ReportDocCreate, ReportDocUpdate

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


async def list_reports(
    session: AsyncSession,
    *,
    owner_id: uuid.UUID,
    search: str = "",
    limit: int = 20,
    offset: int = 0,
) -> tuple[list[Report], int]:
    conditions: list[Any] = [Report.owner_id == owner_id]
    term = search.strip()
    if term:
        pattern = f"%{term}%"
        conditions.append(Report.title.ilike(pattern))

    total = (
        await session.execute(
            select(func.count()).select_from(Report).where(*conditions)
        )
    ).scalar_one()
    rows = await session.execute(
        select(Report)
        .where(*conditions)
        .order_by(Report.updated_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(rows.scalars()), int(total)


async def get_owned(
    session: AsyncSession, *, owner_id: uuid.UUID, report_id: uuid.UUID
) -> Report | None:
    """None for both "missing" and "foreign" — no existence oracle."""
    row = await session.execute(
        select(Report).where(Report.id == report_id, Report.owner_id == owner_id)
    )
    return row.scalar_one_or_none()


async def create(
    session: AsyncSession, *, owner_id: uuid.UUID, data: ReportDocCreate
) -> Report:
    report = Report(owner_id=owner_id, **data.model_dump())
    session.add(report)
    await session.commit()
    await session.refresh(report)
    return report


async def update(
    session: AsyncSession, *, report: Report, data: ReportDocUpdate
) -> Report:
    changes = data.model_dump(exclude_unset=True)
    for field, value in changes.items():
        setattr(report, field, value)
    await session.commit()
    await session.refresh(report)
    return report


async def delete(session: AsyncSession, *, report: Report) -> None:
    await session.delete(report)
    await session.commit()

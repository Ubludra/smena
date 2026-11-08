"""Calendar endpoint: read-only month view over the teacher's own plans,
assignment deadlines and scheduled assessments.

Owner-scoped like every other module; the query parameters are validated so
an out-of-range month answers 422 instead of an empty surprise.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from smena_api.api.deps import get_current_user, get_session
from smena_api.db.models import User
from smena_api.schemas.calendar import CalendarOut
from smena_api.services import calendar as service

router = APIRouter(prefix="/calendar", tags=["calendar"])

SessionDep = Annotated[AsyncSession, Depends(get_session)]
UserDep = Annotated[User, Depends(get_current_user)]


@router.get("", response_model=CalendarOut)
async def get_calendar(
    user: UserDep,
    session: SessionDep,
    year: Annotated[int | None, Query(ge=2000, le=2100)] = None,
    month: Annotated[int | None, Query(ge=1, le=12)] = None,
) -> CalendarOut:
    # Both default to the current month; a lone one of the two is fine too —
    # the other half is taken from "now" as well.
    now_year, now_month = service.current_month()
    resolved_year = year if year is not None else now_year
    resolved_month = month if month is not None else now_month
    return await service.month_events(
        session, owner_id=user.id, year=resolved_year, month=resolved_month
    )

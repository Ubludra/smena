"""Materials endpoints.

Authorization model (one rule, enforced everywhere): the acting user comes
from the verified token; every query is owner-scoped in the service layer.
Foreign or missing ids both answer 404 — the API never confirms the existence
of someone else's material.
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from smena_api.api.deps import get_current_user, get_session
from smena_api.api.routes.safe import require_safe_unlock
from smena_api.db.models import User
from smena_api.schemas.material import (
    MaterialCreate,
    MaterialListOut,
    MaterialOut,
    MaterialUpdate,
)
from smena_api.services import materials as service

router = APIRouter(prefix="/materials", tags=["materials"])

SessionDep = Annotated[AsyncSession, Depends(get_session)]
UserDep = Annotated[User, Depends(get_current_user)]


@router.get("", response_model=MaterialListOut)
async def list_materials(
    request: Request,
    user: UserDep,
    session: SessionDep,
    search: Annotated[str, Query(max_length=200)] = "",
    only_protected: bool = False,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> MaterialListOut:
    if only_protected:
        # The Safe view is gated by the phone unlock (see api/routes/safe.py).
        require_safe_unlock(request, user)
    items, total = await service.list_materials(
        session,
        owner_id=user.id,
        search=search,
        only_protected=only_protected,
        limit=limit,
        offset=offset,
    )
    return MaterialListOut(
        items=[MaterialOut.model_validate(m) for m in items],
        total=total,
    )


@router.post("", response_model=MaterialOut, status_code=status.HTTP_201_CREATED)
async def create_material(body: MaterialCreate, user: UserDep, session: SessionDep) -> MaterialOut:
    material = await service.create(session, owner_id=user.id, data=body)
    return MaterialOut.model_validate(material)


@router.get("/{material_id}", response_model=MaterialOut)
async def get_material(
    material_id: uuid.UUID, request: Request, user: UserDep, session: SessionDep
) -> MaterialOut:
    material = await service.get_owned(session, owner_id=user.id, material_id=material_id)
    if material is None:
        raise _not_found()
    if material.is_protected:
        # Protected content only opens after the Safe unlock — a leaked
        # access token alone cannot read it (direct-id path included).
        require_safe_unlock(request, user)
    return MaterialOut.model_validate(material)


@router.patch("/{material_id}", response_model=MaterialOut)
async def update_material(
    material_id: uuid.UUID, body: MaterialUpdate, user: UserDep, session: SessionDep
) -> MaterialOut:
    material = await service.get_owned(session, owner_id=user.id, material_id=material_id)
    if material is None:
        raise _not_found()
    material = await service.update(session, material, body)
    return MaterialOut.model_validate(material)


@router.delete("/{material_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_material(material_id: uuid.UUID, user: UserDep, session: SessionDep) -> None:
    material = await service.get_owned(session, owner_id=user.id, material_id=material_id)
    if material is None:
        raise _not_found()
    await service.delete(session, material)


def _not_found() -> HTTPException:
    # Same message/code for "missing" and "foreign": no existence oracle.
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Материал не найден",
    )

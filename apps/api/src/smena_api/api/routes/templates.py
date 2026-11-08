"""Templates endpoints.

Same authorization model as the other modules. Payload validation happens in
the schema layer with the target entity's create schema — a template is by
construction a valid input for the entity it creates.
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from smena_api.api.deps import get_current_user, get_session
from smena_api.db.models import User
from smena_api.schemas.template import (
    TemplateCreate,
    TemplateListOut,
    TemplateOut,
    TemplateUpdate,
)
from smena_api.services import templates as service

router = APIRouter(prefix="/templates", tags=["templates"])

SessionDep = Annotated[AsyncSession, Depends(get_session)]
UserDep = Annotated[User, Depends(get_current_user)]


@router.get("", response_model=TemplateListOut)
async def list_templates(
    user: UserDep,
    session: SessionDep,
    entity_type: Annotated[str, Query(max_length=32)] = "",
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> TemplateListOut:
    items, total = await service.list_templates(
        session,
        owner_id=user.id,
        entity_type=entity_type,
        limit=limit,
        offset=offset,
    )
    return TemplateListOut(
        items=[TemplateOut.model_validate(t) for t in items],
        total=total,
    )


@router.post("", response_model=TemplateOut, status_code=status.HTTP_201_CREATED)
async def create_template(
    body: TemplateCreate, user: UserDep, session: SessionDep
) -> TemplateOut:
    template = await service.create(session, owner_id=user.id, data=body)
    return TemplateOut.model_validate(template)


@router.get("/{template_id}", response_model=TemplateOut)
async def get_template(
    template_id: uuid.UUID, user: UserDep, session: SessionDep
) -> TemplateOut:
    # Reads also see built-in system rows; PATCH/DELETE below stay owner-only.
    template = await service.get_visible(
        session, owner_id=user.id, template_id=template_id
    )
    if template is None:
        raise _not_found()
    return TemplateOut.model_validate(template)


@router.patch("/{template_id}", response_model=TemplateOut)
async def update_template(
    template_id: uuid.UUID,
    body: TemplateUpdate,
    user: UserDep,
    session: SessionDep,
) -> TemplateOut:
    template = await service.get_owned(
        session, owner_id=user.id, template_id=template_id
    )
    if template is None:
        raise _not_found()
    template = await service.update(session, template, body)
    return TemplateOut.model_validate(template)


@router.delete("/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_template(
    template_id: uuid.UUID, user: UserDep, session: SessionDep
) -> None:
    template = await service.get_owned(
        session, owner_id=user.id, template_id=template_id
    )
    if template is None:
        raise _not_found()
    await service.delete(session, template)


def _not_found() -> HTTPException:
    # Same message/code for "missing" and "foreign": no existence oracle.
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Шаблон не найден",
    )

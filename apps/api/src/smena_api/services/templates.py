"""Templates business logic.

Ownership discipline as everywhere; the payload was already validated by the
schema layer (same create schemas as the target entities), so the service
only scopes, stores and returns.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

from sqlalchemy import func, or_, select

from smena_api.db.models import Template
from smena_api.schemas.template import TemplateCreate, TemplateUpdate

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


async def list_templates(
    session: AsyncSession,
    *,
    owner_id: uuid.UUID,
    entity_type: str = "",
    limit: int = 20,
    offset: int = 0,
) -> tuple[list[Template], int]:
    conditions: list[Any] = [
        # Own templates plus the built-in system rows (owner_id IS NULL).
        or_(Template.owner_id == owner_id, Template.owner_id.is_(None))
    ]
    if entity_type.strip():
        conditions_where = [Template.entity_type == entity_type.strip()]
        base = select(Template).where(*conditions, *conditions_where)
        count_base = (
            select(func.count()).select_from(Template).where(*conditions, *conditions_where)
        )
    else:
        base = select(Template).where(*conditions)
        count_base = select(func.count()).select_from(Template).where(*conditions)

    total = (await session.execute(count_base)).scalar_one()
    rows = await session.execute(
        base.order_by(Template.updated_at.desc()).limit(limit).offset(offset)
    )
    return list(rows.scalars()), int(total)


async def get_owned(
    session: AsyncSession, *, owner_id: uuid.UUID, template_id: uuid.UUID
) -> Template | None:
    """Only the caller's own row — mutation access. System rows (NULL owner)
    are deliberately excluded: they are read-only for every client."""
    row = await session.execute(
        select(Template).where(Template.id == template_id, Template.owner_id == owner_id)
    )
    return row.scalar_one_or_none()


async def get_visible(
    session: AsyncSession, *, owner_id: uuid.UUID, template_id: uuid.UUID
) -> Template | None:
    """Own or built-in (system) template — read access."""
    row = await session.execute(
        select(Template).where(
            Template.id == template_id,
            (Template.owner_id == owner_id) | (Template.owner_id.is_(None)),
        )
    )
    return row.scalar_one_or_none()


async def create(
    session: AsyncSession, *, owner_id: uuid.UUID, data: TemplateCreate
) -> Template:
    template = Template(owner_id=owner_id, **data.model_dump())
    session.add(template)
    await session.commit()
    await session.refresh(template)
    return template


async def update(
    session: AsyncSession, template: Template, data: TemplateUpdate
) -> Template:
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(template, field, value)
    await session.commit()
    await session.refresh(template)
    return template


async def delete(session: AsyncSession, template: Template) -> None:
    await session.delete(template)
    await session.commit()

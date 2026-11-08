"""Materials business logic.

The service is the *only* place that composes owner-filtered queries; route
handlers never touch query building. This keeps the ownership guarantee
auditable in one file: every function takes ``owner_id`` and filters by it.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import func, or_, select

from smena_api.db.models import Material
from smena_api.schemas.material import MaterialCreate, MaterialUpdate

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


async def list_materials(
    session: AsyncSession,
    *,
    owner_id: uuid.UUID,
    search: str = "",
    only_protected: bool = False,
    limit: int = 20,
    offset: int = 0,
) -> tuple[list[Material], int]:
    """Owner's materials, newest-modified first, with optional filtering."""
    conditions = [Material.owner_id == owner_id]
    if only_protected:
        conditions.append(Material.is_protected.is_(True))
    needle = search.strip()
    if needle:
        pattern = f"%{needle}%"
        conditions.append(or_(Material.title.ilike(pattern), Material.subject.ilike(pattern)))

    total = (
        await session.execute(select(func.count()).select_from(Material).where(*conditions))
    ).scalar_one()
    rows = await session.execute(
        select(Material)
        .where(*conditions)
        .order_by(Material.updated_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(rows.scalars()), int(total)


async def get_owned(
    session: AsyncSession, *, owner_id: uuid.UUID, material_id: uuid.UUID
) -> Material | None:
    """Return the material only if it belongs to ``owner_id``; else None.

    Returning ``None`` for both "missing" and "someone else's" is deliberate:
    the route maps both to 404 so the API never confirms that a foreign id
    exists (existence is itself information).
    """
    row = await session.execute(
        select(Material).where(Material.id == material_id, Material.owner_id == owner_id)
    )
    return row.scalar_one_or_none()


async def create(session: AsyncSession, *, owner_id: uuid.UUID, data: MaterialCreate) -> Material:
    material = Material(owner_id=owner_id, **data.model_dump())
    session.add(material)
    await session.commit()
    await session.refresh(material)
    return material


async def update(session: AsyncSession, material: Material, data: MaterialUpdate) -> Material:
    changes = data.model_dump(exclude_unset=True)
    for field, value in changes.items():
        setattr(material, field, value)
    await session.commit()
    await session.refresh(material)
    return material


async def delete(session: AsyncSession, material: Material) -> None:
    await session.delete(material)
    await session.commit()

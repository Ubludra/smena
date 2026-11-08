"""Assignments business logic.

Same ownership discipline as materials and lesson plans: this service is the
*only* place that composes owner-filtered queries. The related-material link
is validated here too — a teacher may only link an assignment to their own
material, so the lookup is owner-scoped.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

from sqlalchemy import case, func, or_, select

from smena_api.db.models import Assignment, Material
from smena_api.schemas.assignment import AssignmentCreate, AssignmentUpdate

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class RelatedMaterialError(Exception):
    """The linked material is missing or belongs to someone else."""


async def _resolve_related_material(
    session: AsyncSession, *, owner_id: uuid.UUID, material_id: uuid.UUID
) -> uuid.UUID:
    row = await session.execute(
        select(Material.id).where(
            Material.id == material_id, Material.owner_id == owner_id
        )
    )
    if row.scalar_one_or_none() is None:
        raise RelatedMaterialError
    return material_id


async def list_assignments(
    session: AsyncSession,
    *,
    owner_id: uuid.UUID,
    search: str = "",
    status: str = "",
    class_name: str = "",
    subject: str = "",
    limit: int = 20,
    offset: int = 0,
) -> tuple[list[Assignment], int]:
    """Owner's assignments: active by nearest deadline first, then the rest."""
    conditions: list[Any] = [Assignment.owner_id == owner_id]
    needle = search.strip()
    if needle:
        pattern = f"%{needle}%"
        conditions.append(
            or_(Assignment.title.ilike(pattern), Assignment.description.ilike(pattern))
        )
    if status.strip():
        conditions.append(Assignment.status == status.strip())
    class_needle = class_name.strip()
    if class_needle:
        conditions.append(Assignment.class_name.ilike(f"%{class_needle}%"))
    subject_needle = subject.strip()
    if subject_needle:
        conditions.append(Assignment.subject.ilike(f"%{subject_needle}%"))

    total = (
        await session.execute(select(func.count()).select_from(Assignment).where(*conditions))
    ).scalar_one()
    rows = await session.execute(
        select(Assignment)
        .where(*conditions)
        .order_by(
            # Active work with a deadline floats up; archived work sinks.
            case(
                (Assignment.status == "active", 0),
                (Assignment.status == "done", 1),
                else_=2,
            ),
            Assignment.due_at.asc().nulls_last(),
            Assignment.updated_at.desc(),
        )
        .limit(limit)
        .offset(offset)
    )
    return list(rows.scalars()), int(total)


async def get_owned(
    session: AsyncSession, *, owner_id: uuid.UUID, assignment_id: uuid.UUID
) -> Assignment | None:
    """None for both "missing" and "foreign" — no existence oracle."""
    row = await session.execute(
        select(Assignment).where(
            Assignment.id == assignment_id, Assignment.owner_id == owner_id
        )
    )
    return row.scalar_one_or_none()


async def create(
    session: AsyncSession, *, owner_id: uuid.UUID, data: AssignmentCreate
) -> Assignment:
    values = data.model_dump()
    if values["related_material_id"] is not None:
        values["related_material_id"] = await _resolve_related_material(
            session, owner_id=owner_id, material_id=values["related_material_id"]
        )
    assignment = Assignment(owner_id=owner_id, **values)
    session.add(assignment)
    await session.commit()
    await session.refresh(assignment)
    return assignment


async def update(
    session: AsyncSession, assignment: Assignment, data: AssignmentUpdate
) -> Assignment:
    changes = data.model_dump(exclude_unset=True)
    if "related_material_id" in changes and changes["related_material_id"] is not None:
        changes["related_material_id"] = await _resolve_related_material(
            session,
            owner_id=assignment.owner_id,
            material_id=changes["related_material_id"],
        )
    for field, value in changes.items():
        setattr(assignment, field, value)
    await session.commit()
    await session.refresh(assignment)
    return assignment


async def delete(session: AsyncSession, assignment: Assignment) -> None:
    await session.delete(assignment)
    await session.commit()

"""Assessments business logic («Проверочные»).

Ownership discipline as everywhere: every query is owner-filtered here, and
routes never build queries. Questions are replaced as a whole set on update
(simple, predictable authoring semantics); the service re-indexes them
0..n-1 so a malicious or careless client can never set arbitrary ordering.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

from sqlalchemy import func, or_, select

from smena_api.db.models import Assessment, AssessmentQuestion
from smena_api.schemas.assessment import AssessmentCreate, AssessmentUpdate, QuestionIn

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

# «Копия» suffix must survive the 200-char title limit.
_DUPLICATE_SUFFIX = " (копия)"


def _apply_questions(
    assessment: Assessment,
    payload: list[QuestionIn],
) -> None:
    """Replace the question set with re-ordered validated rows."""
    assessment.questions = [
        AssessmentQuestion(
            order_index=index,
            text=question.text,
            type=question.type,
            options=list(question.options),
            correct=list(question.correct),
        )
        for index, question in enumerate(payload)
    ]


async def list_assessments(
    session: AsyncSession,
    *,
    owner_id: uuid.UUID,
    search: str = "",
    class_name: str = "",
    subject: str = "",
    only_protected: bool = False,
    limit: int = 20,
    offset: int = 0,
) -> tuple[list[Assessment], int]:
    """Owner's assessments, newest-modified first, with optional filtering."""
    conditions: list[Any] = [Assessment.owner_id == owner_id]
    if only_protected:
        conditions.append(Assessment.is_protected.is_(True))
    needle = search.strip()
    if needle:
        pattern = f"%{needle}%"
        conditions.append(
            or_(Assessment.title.ilike(pattern), Assessment.description.ilike(pattern))
        )
    class_needle = class_name.strip()
    if class_needle:
        conditions.append(Assessment.class_name.ilike(f"%{class_needle}%"))
    subject_needle = subject.strip()
    if subject_needle:
        conditions.append(Assessment.subject.ilike(f"%{subject_needle}%"))

    total = (
        await session.execute(select(func.count()).select_from(Assessment).where(*conditions))
    ).scalar_one()
    rows = await session.execute(
        select(Assessment)
        .where(*conditions)
        .order_by(Assessment.updated_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(rows.scalars()), int(total)


async def get_owned(
    session: AsyncSession, *, owner_id: uuid.UUID, assessment_id: uuid.UUID
) -> Assessment | None:
    """None for both "missing" and "foreign" — no existence oracle."""
    row = await session.execute(
        select(Assessment).where(
            Assessment.id == assessment_id, Assessment.owner_id == owner_id
        )
    )
    return row.scalar_one_or_none()


async def create(
    session: AsyncSession, *, owner_id: uuid.UUID, data: AssessmentCreate
) -> Assessment:
    values = data.model_dump(exclude={"questions"})
    assessment = Assessment(owner_id=owner_id, **values)
    _apply_questions(assessment, data.questions)
    session.add(assessment)
    await session.commit()
    await session.refresh(assessment)
    return assessment


async def update(
    session: AsyncSession, assessment: Assessment, data: AssessmentUpdate
) -> Assessment:
    changes = data.model_dump(exclude_unset=True)
    has_new_questions = "questions" in changes
    changes.pop("questions", None)
    for field, value in changes.items():
        setattr(assessment, field, value)
    if has_new_questions and data.questions is not None:
        # data.questions keeps validated QuestionIn objects (model_dump
        # would have reduced them to dicts).
        _apply_questions(assessment, data.questions)
    await session.commit()
    await session.refresh(assessment)
    return assessment


async def duplicate(session: AsyncSession, assessment: Assessment) -> Assessment:
    """Copy the assessment with its questions as new rows, same owner."""
    base_title = assessment.title.removesuffix(_DUPLICATE_SUFFIX)
    max_base = 200 - len(_DUPLICATE_SUFFIX)
    copy = Assessment(
        owner_id=assessment.owner_id,
        title=f"{base_title[:max_base].rstrip()}{_DUPLICATE_SUFFIX}",
        description=assessment.description,
        subject=assessment.subject,
        class_name=assessment.class_name,
        scheduled_at=assessment.scheduled_at,
        duration_minutes=assessment.duration_minutes,
        is_protected=assessment.is_protected,
        questions=[
            AssessmentQuestion(
                order_index=question.order_index,
                text=question.text,
                type=question.type,
                options=list(question.options),
                correct=list(question.correct),
            )
            for question in assessment.questions
        ],
    )
    session.add(copy)
    await session.commit()
    await session.refresh(copy)
    return copy


async def delete(session: AsyncSession, assessment: Assessment) -> None:
    await session.delete(assessment)
    await session.commit()

"""Schemas for the assessments feature («Проверочные»).

Question payloads are fully validated server-side: type-specific rules
(options for choice types, key indexes in range) are checked here, so an
arbitrary JSON body never reaches the ORM as-is.
"""

import uuid
from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

Title = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=200),
]
Subject = Annotated[str, StringConstraints(strip_whitespace=True, max_length=120)]
ClassName = Annotated[str, StringConstraints(strip_whitespace=True, max_length=32)]
LongText = Annotated[str, StringConstraints(max_length=5_000)]
QuestionText = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=2_000),
]
QuestionType = Literal["single", "multi", "text"]
OptionText = Annotated[str, StringConstraints(max_length=300)]


class QuestionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: QuestionText
    type: QuestionType
    options: Annotated[list[OptionText], Field(max_length=10)] = []
    correct: list[Any] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_by_type(self) -> "QuestionIn":
        if self.type == "text":
            if self.options:
                raise ValueError("Текстовый вопрос не имеет вариантов ответа")
            if not self.correct or any(not isinstance(k, str) for k in self.correct):
                raise ValueError(
                    "Ключ текстового вопроса — непустой список строк (эталон ответа)"
                )
            return self

        if len(self.options) < 2:
            raise ValueError("Нужно минимум 2 варианта ответа")
        if not self.correct:
            raise ValueError("Укажите правильный ответ")
        for key in self.correct:
            if not isinstance(key, int) or not 0 <= key < len(self.options):
                raise ValueError("Ключ ответа — индекс варианта вне диапазона")
        expected_single = 1 if self.type == "single" else None
        if expected_single is not None and len(self.correct) != 1:
            raise ValueError("У вопроса с одним ответом ровно один ключ")
        return self


class AssessmentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: Title
    description: LongText = ""
    subject: Subject = ""
    class_name: ClassName = ""
    scheduled_at: datetime | None = None
    duration_minutes: Annotated[int, Field(ge=1, le=600)] | None = None
    is_protected: bool = False
    questions: Annotated[list[QuestionIn], Field(max_length=50)] = []


class AssessmentUpdate(BaseModel):
    """Partial update; ``questions`` replaces the whole set when provided."""

    model_config = ConfigDict(extra="forbid")

    title: Title | None = None
    description: LongText | None = None
    subject: Subject | None = None
    class_name: ClassName | None = None
    scheduled_at: datetime | None = None
    duration_minutes: Annotated[int, Field(ge=1, le=600)] | None = None
    is_protected: bool | None = None
    questions: Annotated[list[QuestionIn], Field(max_length=50)] | None = None


class QuestionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    text: str
    type: QuestionType
    options: list[Any]
    correct: list[Any]


class AssessmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    description: str
    subject: str
    class_name: str
    scheduled_at: datetime | None
    duration_minutes: int | None
    is_protected: bool
    questions: list[QuestionOut]
    created_at: datetime
    updated_at: datetime


class AssessmentListOut(BaseModel):
    items: list[AssessmentOut]
    total: int = Field(description="Total number of matches, ignoring pagination.")

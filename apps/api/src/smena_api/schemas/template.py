"""Schemas for the templates feature.

``payload`` is not trusted: it is re-validated through the *same* create
schema of the target entity on every write (create and update). The stored
document is therefore always a valid input for the entity's create endpoint.
"""

import uuid
from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from smena_api.schemas.assessment import AssessmentCreate
from smena_api.schemas.assignment import AssignmentCreate
from smena_api.schemas.lesson_plan import LessonPlanCreate
from smena_api.schemas.material import MaterialCreate

TemplateEntityType = Literal["lesson_plan", "assignment", "assessment", "report"]

_PAYLOAD_SCHEMAS: dict[str, type[BaseModel]] = {
    "lesson_plan": LessonPlanCreate,
    "assignment": AssignmentCreate,
    "assessment": AssessmentCreate,
    "report": MaterialCreate,
}

# ``report`` templates are built-in system rows only (seed migration): a
# client must never mint one, so create/update reject the type outright.
CLIENT_CREATABLE_TYPES = ("lesson_plan", "assignment", "assessment")

# Per-type payload size ceiling: the create schemas bound every field, but a
# runaway JSON body should be rejected before deep validation.
PAYLOAD_MAX_BYTES = 64_000


class TemplateBase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=1, max_length=200),
    ]
    entity_type: TemplateEntityType


class TemplateCreate(TemplateBase):
    payload: dict[str, Any]

    @model_validator(mode="after")
    def validate_payload(self) -> "TemplateCreate":
        if self.entity_type not in CLIENT_CREATABLE_TYPES:
            raise ValueError("Такой тип шаблона нельзя создать вручную")
        schema = _PAYLOAD_SCHEMAS[self.entity_type]
        try:
            schema.model_validate(self.payload)
        except Exception as error:
            raise ValueError(f"payload не подходит для {self.entity_type}: {error}") from error
        return self


class TemplateUpdate(BaseModel):
    """Partial update; a new payload is re-validated for the (possibly new) type."""

    model_config = ConfigDict(extra="forbid")

    name: Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=1, max_length=200),
    ] | None = None
    entity_type: TemplateEntityType | None = None
    payload: dict[str, Any] | None = None

    @model_validator(mode="after")
    def validate_payload(self) -> "TemplateUpdate":
        if self.entity_type is not None and self.entity_type not in CLIENT_CREATABLE_TYPES:
            raise ValueError("Такой тип шаблона нельзя установить")
        if self.payload is not None:
            schema = _PAYLOAD_SCHEMAS[self.entity_type or "lesson_plan"]
            try:
                schema.model_validate(self.payload)
            except Exception as error:
                raise ValueError(
                    f"payload не подходит для {self.entity_type}: {error}"
                ) from error
        return self


class TemplateOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    entity_type: TemplateEntityType
    payload: dict[str, Any]
    # True for seeded system rows (owner_id IS NULL): read-only for clients.
    is_system: bool
    created_at: datetime
    updated_at: datetime


class TemplateListOut(BaseModel):
    items: list[TemplateOut]
    total: int = Field(description="Total number of matches, ignoring pagination.")

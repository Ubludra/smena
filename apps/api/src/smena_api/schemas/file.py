"""Schemas for the files feature (metadata only — bytes never pass through
Pydantic; they stream through the upload/download endpoints)."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class FileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    original_name: str
    mime_type: str
    size_bytes: int
    created_at: datetime
    material_id: uuid.UUID | None = None
    lesson_plan_id: uuid.UUID | None = None
    assessment_id: uuid.UUID | None = None
    assignment_id: uuid.UUID | None = None
    report_id: uuid.UUID | None = None


class FileListOut(BaseModel):
    items: list[FileOut]
    total: int

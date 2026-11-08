"""Files endpoints: multipart upload, owner-scoped list/download/delete.

Downloads are served through the API with the verified token — the stored
blobs are never exposed as a static mount. Foreign and missing ids answer
the same 404 (no existence oracle), as in every other module.
"""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable
from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    Form,
    HTTPException,
    Query,
    Request,
    UploadFile,
    status,
)
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from smena_api.api.deps import get_current_user, get_session
from smena_api.config import Settings, get_settings
from smena_api.db.models import User
from smena_api.schemas.file import FileListOut, FileOut
from smena_api.services import assessments as assessments_service
from smena_api.services import assignments as assignments_service
from smena_api.services import files as service
from smena_api.services import lesson_plans as lesson_plans_service
from smena_api.services import materials as materials_service
from smena_api.services import report_docs as report_docs_service

router = APIRouter(prefix="/files", tags=["files"])

SessionDep = Annotated[AsyncSession, Depends(get_session)]
UserDep = Annotated[User, Depends(get_current_user)]
SettingsDep = Annotated[Settings, Depends(get_settings)]

# Every workspace entity a file can be attached to: query/form field name ->
# (ownership getter, 404 message). The getter kwarg is the field itself.
# Call signature is identical (session, owner_id=..., <field>=...); the model
# each getter returns differs, hence the deliberate loose callable type.
_OwnershipGetter = Callable[..., Awaitable[object | None]]
_OWNERSHIP_CHECKS: dict[str, tuple[_OwnershipGetter, str]] = {
    "material_id": (materials_service.get_owned, "Материал не найден"),
    "lesson_plan_id": (lesson_plans_service.get_owned, "План не найден"),
    "assessment_id": (assessments_service.get_owned, "Проверочная не найдена"),
    "assignment_id": (assignments_service.get_owned, "Задание не найдено"),
    "report_id": (report_docs_service.get_owned, "Отчёт не найден"),
}


async def _resolve_target(
    session: AsyncSession, *, owner_id: uuid.UUID, field: str, raw: str | None
) -> uuid.UUID | None:
    """Validate one optional target field: parse the id, prove ownership.

    Foreign and missing ids answer the same 404 (no existence oracle) —
    before any bytes are written.
    """
    if raw is None or not raw.strip():
        return None
    getter, not_found = _OWNERSHIP_CHECKS[field]
    try:
        target_id = uuid.UUID(raw.strip())
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"{field} должен быть корректным идентификатором",
        ) from None
    if await getter(session, owner_id=owner_id, **{field: target_id}) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=not_found)
    return target_id


@router.get("", response_model=FileListOut)
async def list_files(
    user: UserDep,
    session: SessionDep,
    material_id: Annotated[uuid.UUID | None, Query()] = None,
    lesson_plan_id: Annotated[uuid.UUID | None, Query()] = None,
    assessment_id: Annotated[uuid.UUID | None, Query()] = None,
    assignment_id: Annotated[uuid.UUID | None, Query()] = None,
    report_id: Annotated[uuid.UUID | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> FileListOut:
    items, total = await service.list_files(
        session,
        owner_id=user.id,
        material_id=material_id,
        lesson_plan_id=lesson_plan_id,
        assessment_id=assessment_id,
        assignment_id=assignment_id,
        report_id=report_id,
        limit=limit,
        offset=offset,
    )
    return FileListOut(items=[FileOut.model_validate(f) for f in items], total=total)


@router.post("", response_model=FileOut, status_code=status.HTTP_201_CREATED)
async def upload_file(
    request: Request,
    user: UserDep,
    session: SessionDep,
    upload: UploadFile,
    settings: SettingsDep,
    material_id: Annotated[str | None, Form()] = None,
    lesson_plan_id: Annotated[str | None, Form()] = None,
    assessment_id: Annotated[str | None, Form()] = None,
    assignment_id: Annotated[str | None, Form()] = None,
    report_id: Annotated[str | None, Form()] = None,
) -> FileOut:
    """Multipart upload. One file per request; size/type limits enforced.

    Any of the entity id fields optionally attaches the file to an entity the
    caller owns (material, lesson plan, assessment, assignment, report);
    a foreign or missing id answers 404 before anything is written.
    """
    del request  # kept for symmetry with other endpoints (no body model)
    links = {
        field: await _resolve_target(
            session, owner_id=user.id, field=field, raw=raw
        )
        for field, raw in (
            ("material_id", material_id),
            ("lesson_plan_id", lesson_plan_id),
            ("assessment_id", assessment_id),
            ("assignment_id", assignment_id),
            ("report_id", report_id),
        )
    }
    try:
        file_row = await service.save_upload(
            session,
            owner_id=user.id,
            upload=upload,
            upload_dir=settings.upload_dir,
            max_bytes=settings.upload_max_bytes,
            **links,
        )
    except service.UnsupportedFileTypeError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Тип файла не поддерживается. Разрешены документы, таблицы, "
            "презентации, PDF, изображения и zip.",
        ) from None
    except service.FileTooLargeError as error:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Файл больше {error.max_bytes // (1024 * 1024)} МБ",
        ) from None
    except service.EmptyFileError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Файл пустой",
        ) from None
    return FileOut.model_validate(file_row)


@router.get("/{file_id}/download")
async def download_file(
    file_id: uuid.UUID, user: UserDep, session: SessionDep, settings: SettingsDep
) -> FileResponse:
    file_row = await service.get_owned(session, owner_id=user.id, file_id=file_id)
    if file_row is None:
        raise _not_found()
    path = service.open_stored(settings.upload_dir, file_row.stored_name)
    if not path.is_file():  # pragma: no cover — row and blob are kept in sync
        raise _not_found()
    # original_name is sanitized at write time (basename, no control chars),
    # so echoing it into the header is safe.
    return FileResponse(
        path,
        media_type=file_row.mime_type or "application/octet-stream",
        filename=file_row.original_name,
    )


@router.delete("/{file_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_file(
    file_id: uuid.UUID, user: UserDep, session: SessionDep, settings: SettingsDep
) -> None:
    file_row = await service.get_owned(session, owner_id=user.id, file_id=file_id)
    if file_row is None:
        raise _not_found()
    await service.delete(session, file_row, settings.upload_dir)


def _not_found() -> HTTPException:
    # Same message/code for "missing" and "foreign": no existence oracle.
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Файл не найден",
    )

"""File storage logic: stream-to-disk upload, owner-scoped metadata.

Security posture:

* the stored name is always generated here (``uuid4`` + a normalised
  extension) — the client can never influence the storage path;
* the original name is reduced to a basename and stripped of control
  characters before it is ever stored or echoed into a Content-Disposition;
* upload size is enforced while streaming chunks, so an oversized body is
  rejected (413) without buffering it whole;
* every read/delete is owner-scoped; foreign ids answer 404 with no
  existence oracle, and downloads go through the API (auth required), never
  a static file mount.
"""

from __future__ import annotations

import contextlib
import re
import uuid
from pathlib import Path
from typing import TYPE_CHECKING

from sqlalchemy import func, select

from smena_api.db.models import UploadedFile

if TYPE_CHECKING:
    from fastapi import UploadFile
    from sqlalchemy.ext.asyncio import AsyncSession

# Extensions we accept. An allowlist is the honest default for a teaching
# workspace: documents, sheets, slides, PDFs and images. Anything else is
# rejected with 422 rather than stored "for later".
ALLOWED_EXTENSIONS = frozenset(
    {
        ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".odt", ".ods",
        ".odp", ".txt", ".md", ".csv", ".png", ".jpg", ".jpeg", ".gif", ".webp",
        ".svg", ".zip",
    }
)

# Collapse anything suspicious out of the client-provided filename.
_UNSAFE_NAME_CHARS = re.compile(r"[^\w.\-() ]+", re.UNICODE)


def sanitize_original_name(raw: str) -> str:
    """Basename + control-char strip + length clamp; never empty afterwards."""
    name = Path(raw.replace("\\", "/")).name
    name = "".join(ch for ch in name if ch.isprintable()).strip()
    name = _UNSAFE_NAME_CHARS.sub("_", name).strip(". ")
    if name == "":
        name = "file"
    return name[:255]


def extension_of(raw_name: str) -> str:
    """Lowercased extension with a leading dot; empty when absent."""
    name = sanitize_original_name(raw_name)
    suffix = Path(name).suffix.lower()
    return suffix if suffix in ALLOWED_EXTENSIONS else ""


def stored_name_for(extension: str) -> str:
    return f"{uuid.uuid4().hex}{extension}"


def _storage_path(upload_dir: str, stored_name: str) -> Path:
    # Defense in depth: stored_name is server-generated ("<hex>.<ext>"), but
    # assert the shape so a future refactor cannot smuggle a path in.
    if "/" in stored_name or "\\" in stored_name or stored_name.startswith("."):
        raise ValueError("stored name must be a bare filename")
    return Path(upload_dir) / stored_name


async def save_upload(
    session: AsyncSession,
    *,
    owner_id: uuid.UUID,
    upload: UploadFile,
    upload_dir: str,
    max_bytes: int,
    material_id: uuid.UUID | None = None,
    lesson_plan_id: uuid.UUID | None = None,
    assessment_id: uuid.UUID | None = None,
    assignment_id: uuid.UUID | None = None,
    report_id: uuid.UUID | None = None,
) -> UploadedFile:
    """Stream the upload to ``upload_dir`` and register it. Raises:

    ``UnsupportedFileTypeError`` — extension not in the allowlist;
    ``FileTooLargeError`` — body exceeds ``max_bytes``;
    ``EmptyFileError`` — zero bytes.
    """
    extension = extension_of(upload.filename or "")
    if extension == "":
        raise UnsupportedFileTypeError(upload.filename or "")

    destination = _storage_path(upload_dir, stored_name_for(extension))
    destination.parent.mkdir(parents=True, exist_ok=True)

    # Write via a private temp file, then atomically rename: a crashed upload
    # leaves no half-written blob with a final name.
    temp_path = destination.with_name(f".{destination.name}.part")
    size = 0
    try:
        with temp_path.open("wb") as sink:
            while True:
                chunk = await upload.read(64 * 1024)
                if not chunk:
                    break
                size += len(chunk)
                if size > max_bytes:
                    raise FileTooLargeError(max_bytes)
                sink.write(chunk)
        if size == 0:
            raise EmptyFileError
        temp_path.replace(destination)
    finally:
        temp_path.unlink(missing_ok=True)

    file_row = UploadedFile(
        owner_id=owner_id,
        original_name=sanitize_original_name(upload.filename or "file"),
        stored_name=destination.name,
        mime_type=(upload.content_type or "")[:127],
        size_bytes=size,
        # Ownership of each target entity is verified by the route before
        # anything is written — the service never trusts a bare uuid.
        material_id=material_id,
        lesson_plan_id=lesson_plan_id,
        assessment_id=assessment_id,
        assignment_id=assignment_id,
        report_id=report_id,
    )
    session.add(file_row)
    await session.commit()
    await session.refresh(file_row)
    return file_row


def open_stored(upload_dir: str, stored_name: str) -> Path:
    """Path to the stored blob, after the same shape check as at write time."""
    return _storage_path(upload_dir, stored_name)


def remove_stored(upload_dir: str, stored_name: str) -> None:
    """Best-effort blob removal; the DB row is already gone by then."""
    with contextlib.suppress(OSError):
        _storage_path(upload_dir, stored_name).unlink(missing_ok=True)


async def list_files(
    session: AsyncSession,
    *,
    owner_id: uuid.UUID,
    material_id: uuid.UUID | None = None,
    lesson_plan_id: uuid.UUID | None = None,
    assessment_id: uuid.UUID | None = None,
    assignment_id: uuid.UUID | None = None,
    report_id: uuid.UUID | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[UploadedFile], int]:
    conditions = [UploadedFile.owner_id == owner_id]
    for column, value in (
        (UploadedFile.material_id, material_id),
        (UploadedFile.lesson_plan_id, lesson_plan_id),
        (UploadedFile.assessment_id, assessment_id),
        (UploadedFile.assignment_id, assignment_id),
        (UploadedFile.report_id, report_id),
    ):
        if value is not None:
            conditions.append(column == value)
    total = (
        await session.execute(
            select(func.count()).select_from(UploadedFile).where(*conditions)
        )
    ).scalar_one()
    rows = await session.execute(
        select(UploadedFile)
        .where(*conditions)
        .order_by(UploadedFile.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(rows.scalars()), int(total)


async def get_owned(
    session: AsyncSession, *, owner_id: uuid.UUID, file_id: uuid.UUID
) -> UploadedFile | None:
    """None for both "missing" and "foreign" — no existence oracle."""
    row = await session.execute(
        select(UploadedFile).where(
            UploadedFile.id == file_id, UploadedFile.owner_id == owner_id
        )
    )
    return row.scalar_one_or_none()


async def delete(session: AsyncSession, file_row: UploadedFile, upload_dir: str) -> None:
    await session.delete(file_row)
    await session.commit()
    remove_stored(upload_dir, file_row.stored_name)


class UnsupportedFileTypeError(Exception):
    def __init__(self, filename: str) -> None:
        super().__init__(filename)
        self.filename = filename


class FileTooLargeError(Exception):
    def __init__(self, max_bytes: int) -> None:
        super().__init__(max_bytes)
        self.max_bytes = max_bytes


class EmptyFileError(Exception):
    pass

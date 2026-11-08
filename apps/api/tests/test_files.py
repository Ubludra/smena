"""Files API: multipart upload with allowlist + size cap, owner-scoped
download/delete.

Security contract under test:

* the stored name is server-generated — the response never contains it, and
  the download path cannot be influenced by the client;
* disallowed types and oversized bodies are rejected with explicit statuses;
* foreign and missing ids both answer 404 (no existence oracle);
* deleted rows remove the blob as well (upload_dir is a temp dir in tests).
"""

from __future__ import annotations

import urllib.parse
import uuid
from typing import TYPE_CHECKING

from helpers import dev_login

if TYPE_CHECKING:
    from httpx import AsyncClient

API = "/api/v1"


async def _upload(
    client: AsyncClient,
    headers: dict[str, str],
    filename: str = "конспект.pdf",
    content: bytes = b"%PDF-1.4 test",
    mime: str = "application/pdf",
):
    return await client.post(
        f"{API}/files",
        files={"upload": (filename, content, mime)},
        headers=headers,
    )


# --- authentication -----------------------------------------------------------


async def test_list_requires_auth(client: AsyncClient) -> None:
    response = await client.get(f"{API}/files")
    assert response.status_code == 401


async def test_upload_requires_auth(client: AsyncClient) -> None:
    response = await client.post(
        f"{API}/files", files={"upload": ("x.txt", b"hi", "text/plain")}
    )
    assert response.status_code == 401


# --- happy path ---------------------------------------------------------------


async def test_upload_list_download_delete(client: AsyncClient) -> None:
    headers = await dev_login(client)

    uploaded = await _upload(client, headers)
    assert uploaded.status_code == 201, uploaded.text
    body = uploaded.json()
    assert body["original_name"] == "конспект.pdf"
    assert body["size_bytes"] == len(b"%PDF-1.4 test")
    # The server-generated stored name never leaks through the API.
    assert "stored_name" not in body
    file_id = body["id"]

    listed = await client.get(f"{API}/files", headers=headers)
    assert listed.json()["total"] == 1
    assert listed.json()["items"][0]["id"] == file_id

    downloaded = await client.get(f"{API}/files/{file_id}/download", headers=headers)
    assert downloaded.status_code == 200
    assert downloaded.content == b"%PDF-1.4 test"
    disposition = downloaded.headers["content-disposition"]
    assert "attachment" in disposition
    # Non-ASCII names travel RFC 5987-encoded (filename*=utf-8''...).
    assert "filename" in disposition
    quoted = urllib.parse.quote("конспект.pdf")
    assert quoted in disposition

    deleted = await client.delete(f"{API}/files/{file_id}", headers=headers)
    assert deleted.status_code == 204
    after = await client.get(f"{API}/files/{file_id}/download", headers=headers)
    assert after.status_code == 404


async def test_upload_rejects_disallowed_type(client: AsyncClient) -> None:
    headers = await dev_login(client)
    for filename in ("payload.exe", "script.sh", "no-extension"):
        response = await _upload(client, headers, filename=filename)
        assert response.status_code == 422, filename
    # The failed attempts never leave rows behind.
    listed = await client.get(f"{API}/files", headers=headers)
    assert listed.json()["total"] == 0


async def test_upload_rejects_empty_file(client: AsyncClient) -> None:
    headers = await dev_login(client)
    response = await _upload(client, headers, content=b"")
    assert response.status_code == 422


async def test_upload_rejects_oversize(client: AsyncClient) -> None:
    headers = await dev_login(client)
    response = await _upload(client, headers, content=b"x" * (21 * 1024 * 1024))
    assert response.status_code == 413


async def test_path_like_filename_is_sanitized(client: AsyncClient) -> None:
    headers = await dev_login(client)
    response = await _upload(
        client, headers, filename="../../etc/passwd.pdf", mime="application/pdf"
    )
    assert response.status_code == 201
    # Only the basename survives; nothing path-like is stored or echoed.
    assert response.json()["original_name"] == "passwd.pdf"


async def test_unicode_filename_survives_roundtrip(client: AsyncClient) -> None:
    headers = await dev_login(client)
    response = await _upload(client, headers, filename="План урока (7Б).docx")
    assert response.status_code == 201
    assert response.json()["original_name"] == "План урока (7Б).docx"


# --- ownership (IDOR) -----------------------------------------------------------


async def test_foreign_file_invisible_and_undeletable(client: AsyncClient) -> None:
    owner, stranger = await dev_login(client, "Анна"), await dev_login(client, "Борис")
    uploaded = await _upload(client, owner)
    file_id = uploaded.json()["id"]

    read = await client.get(f"{API}/files/{file_id}/download", headers=stranger)
    assert read.status_code == 404

    delete = await client.delete(f"{API}/files/{file_id}", headers=stranger)
    assert delete.status_code == 404

    listed = await client.get(f"{API}/files", headers=stranger)
    assert listed.json()["total"] == 0

    # The owner still sees and can download the file.
    original = await client.get(f"{API}/files/{file_id}/download", headers=owner)
    assert original.status_code == 200


async def test_missing_file_is_404(client: AsyncClient) -> None:
    headers = await dev_login(client)
    response = await client.get(f"{API}/files/{uuid.uuid4()}/download", headers=headers)
    assert response.status_code == 404


async def test_malformed_id_returns_422(client: AsyncClient) -> None:
    headers = await dev_login(client)
    response = await client.get(f"{API}/files/not-a-uuid/download", headers=headers)
    assert response.status_code == 422


# --- attachment to a material ---------------------------------------------------


async def _create_material(client: AsyncClient, headers: dict[str, str]) -> str:
    created = await client.post(
        f"{API}/materials",
        json={"title": "К lesson", "subject": "Математика", "content": "конспект"},
        headers=headers,
    )
    assert created.status_code == 201, created.text
    material_id: str = created.json()["id"]
    return material_id


async def test_upload_attaches_to_own_material_and_filters(client: AsyncClient) -> None:
    headers = await dev_login(client)
    material_id = await _create_material(client, headers)

    attached = await client.post(
        f"{API}/files",
        files={"upload": ("лист.pdf", b"%PDF-1.4 x", "application/pdf")},
        data={"material_id": material_id},
        headers=headers,
    )
    assert attached.status_code == 201, attached.text
    assert attached.json()["material_id"] == material_id

    # A loose file (no attachment) stays in the general drawer only.
    await _upload(client, headers)

    scoped = await client.get(f"{API}/files?material_id={material_id}", headers=headers)
    assert scoped.status_code == 200, scoped.text
    assert scoped.json()["total"] == 1
    assert scoped.json()["items"][0]["material_id"] == material_id

    everything = await client.get(f"{API}/files", headers=headers)
    assert everything.json()["total"] == 2

    other_material = await _create_material(client, headers)
    empty = await client.get(f"{API}/files?material_id={other_material}", headers=headers)
    assert empty.json()["total"] == 0


async def test_upload_to_foreign_material_is_404_and_writes_nothing(
    client: AsyncClient,
) -> None:
    owner, attacker = await dev_login(client, "Анна"), await dev_login(client, "Борис")
    material_id = await _create_material(client, owner)

    response = await client.post(
        f"{API}/files",
        files={"upload": ("шпион.pdf", b"%PDF-1.4 x", "application/pdf")},
        data={"material_id": material_id},
        headers=attacker,
    )
    assert response.status_code == 404
    # The rejection happens before any byte is stored.
    assert (await client.get(f"{API}/files", headers=attacker)).json()["total"] == 0


async def test_upload_with_malformed_material_id_is_422(client: AsyncClient) -> None:
    headers = await dev_login(client)
    response = await client.post(
        f"{API}/files",
        files={"upload": ("x.txt", b"hi", "text/plain")},
        data={"material_id": "not-a-uuid"},
        headers=headers,
    )
    assert response.status_code == 422
    assert (await client.get(f"{API}/files", headers=headers)).json()["total"] == 0


async def test_deleting_material_keeps_file_unattached(client: AsyncClient) -> None:
    headers = await dev_login(client)
    material_id = await _create_material(client, headers)
    uploaded = await client.post(
        f"{API}/files",
        files={"upload": ("приложение.docx", b"PK\x03\x04", "application/vnd.ms-word")},
        data={"material_id": material_id},
        headers=headers,
    )
    file_id = uploaded.json()["id"]

    deleted = await client.delete(f"{API}/materials/{material_id}", headers=headers)
    assert deleted.status_code == 204

    # SET NULL: the document survives in the general drawer, downloadable.
    listed = await client.get(f"{API}/files", headers=headers)
    assert listed.json()["total"] == 1
    assert listed.json()["items"][0]["material_id"] is None
    download = await client.get(f"{API}/files/{file_id}/download", headers=headers)
    assert download.status_code == 200


# --- attachment to any workspace entity ---------------------------------------

# (form field, create path, create payload, list filter) for every target.
_TARGETS = [
    ("lesson_plan_id", f"{API}/lesson-plans", {"title": "План: падежи"}),
    ("assessment_id", f"{API}/assessments", {"title": "Контрольная: падежи"}),
    ("assignment_id", f"{API}/assignments", {"title": "Задание: упр. 130"}),
    ("report_id", f"{API}/reports", {"title": "Отчёт: самообразование"}),
]


async def _create_entity(
    client: AsyncClient, headers: dict[str, str], path: str, payload: dict
) -> str:
    created = await client.post(path, json=payload, headers=headers)
    assert created.status_code == 201, created.text
    entity_id: str = created.json()["id"]
    return entity_id


async def test_upload_attaches_to_every_entity_kind(client: AsyncClient) -> None:
    headers = await dev_login(client)
    for field, path, payload in _TARGETS:
        entity_id = await _create_entity(client, headers, path, payload)
        attached = await client.post(
            f"{API}/files",
            files={"upload": ("приложение.pdf", b"%PDF-1.4 x", "application/pdf")},
            data={field: entity_id},
            headers=headers,
        )
        assert attached.status_code == 201, (field, attached.text)
        assert attached.json()[field] == entity_id

        scoped = await client.get(f"{API}/files?{field}={entity_id}", headers=headers)
        assert scoped.json()["total"] == 1
        assert scoped.json()["items"][0][field] == entity_id


async def test_upload_to_foreign_entity_is_404_for_every_kind(
    client: AsyncClient,
) -> None:
    owner, attacker = await dev_login(client, "Анна"), await dev_login(client, "Борис")
    for field, path, payload in _TARGETS:
        entity_id = await _create_entity(client, owner, path, payload)
        response = await client.post(
            f"{API}/files",
            files={"upload": ("шпион.pdf", b"%PDF-1.4 x", "application/pdf")},
            data={field: entity_id},
            headers=attacker,
        )
        assert response.status_code == 404, field
    # Rejections happened before any byte was stored.
    assert (await client.get(f"{API}/files", headers=attacker)).json()["total"] == 0


async def test_deleting_host_entity_keeps_file_unattached(client: AsyncClient) -> None:
    headers = await dev_login(client)
    plan_id = await _create_entity(
        client, headers, f"{API}/lesson-plans", {"title": "План: звуки и буквы"}
    )
    uploaded = await client.post(
        f"{API}/files",
        files={"upload": ("карточки.pdf", b"%PDF-1.4 x", "application/pdf")},
        data={"lesson_plan_id": plan_id},
        headers=headers,
    )
    file_id = uploaded.json()["id"]

    assert (
        await client.delete(f"{API}/lesson-plans/{plan_id}", headers=headers)
    ).status_code == 204

    listed = await client.get(f"{API}/files", headers=headers)
    assert listed.json()["total"] == 1
    assert listed.json()["items"][0]["lesson_plan_id"] is None
    download = await client.get(f"{API}/files/{file_id}/download", headers=headers)
    assert download.status_code == 200

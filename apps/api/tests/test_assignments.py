"""Assignments API: CRUD, filtering, status transitions, ownership, validation.

Same guarantees as the other modules: ownership enforced in the service layer,
foreign and missing ids both answer 404, and a related-material link is only
accepted when it points at the owner's own library.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from helpers import dev_login

if TYPE_CHECKING:
    from httpx import AsyncClient

API = "/api/v1"

ASSIGNMENT = {
    "title": "Задание: упр. 120",
    "description": "Параграф 14, упражнения 120–124",
    "subject": "Русский язык",
    "class_name": "6А",
    "due_at": "2026-11-01T18:00:00+00:00",
}


async def _create(client: AsyncClient, headers: dict[str, str], **overrides) -> dict:
    payload = {**ASSIGNMENT, **overrides}
    response = await client.post(f"{API}/assignments", json=payload, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


async def _create_material(client: AsyncClient, headers: dict[str, str]) -> dict:
    response = await client.post(
        f"{API}/materials",
        json={"title": "Справочник", "subject": "", "content": "", "is_protected": False},
        headers=headers,
    )
    assert response.status_code == 201
    return response.json()


# --- authentication -----------------------------------------------------------


async def test_list_requires_auth(client: AsyncClient) -> None:
    response = await client.get(f"{API}/assignments")
    assert response.status_code == 401


async def test_empty_list_for_new_teacher(client: AsyncClient) -> None:
    headers = await dev_login(client)
    response = await client.get(f"{API}/assignments", headers=headers)
    assert response.status_code == 200
    assert response.json() == {"items": [], "total": 0}


# --- CRUD happy path ----------------------------------------------------------


async def test_create_read_update_delete(client: AsyncClient) -> None:
    headers = await dev_login(client)
    assignment = await _create(client, headers)
    assignment_id = assignment["id"]

    assert assignment["status"] == "active"
    assert assignment["due_at"].startswith("2026-11-01T18:00")

    fetched = await client.get(f"{API}/assignments/{assignment_id}", headers=headers)
    assert fetched.status_code == 200
    assert fetched.json()["title"] == "Задание: упр. 120"

    patched = await client.patch(
        f"{API}/assignments/{assignment_id}",
        json={"title": "Задание: упр. 125", "status": "done"},
        headers=headers,
    )
    assert patched.status_code == 200
    assert patched.json()["status"] == "done"
    # Untouched fields survive a partial update.
    assert patched.json()["description"] == ASSIGNMENT["description"]

    deleted = await client.delete(f"{API}/assignments/{assignment_id}", headers=headers)
    assert deleted.status_code == 204
    after = await client.get(f"{API}/assignments/{assignment_id}", headers=headers)
    assert after.status_code == 404


async def test_status_transitions(client: AsyncClient) -> None:
    headers = await dev_login(client)
    assignment = await _create(client, headers)

    done = await client.patch(
        f"{API}/assignments/{assignment['id']}",
        json={"status": "done"},
        headers=headers,
    )
    assert done.json()["status"] == "done"

    archived = await client.patch(
        f"{API}/assignments/{assignment['id']}",
        json={"status": "archived"},
        headers=headers,
    )
    assert archived.json()["status"] == "archived"

    back = await client.patch(
        f"{API}/assignments/{assignment['id']}",
        json={"status": "active"},
        headers=headers,
    )
    assert back.json()["status"] == "active"


# --- related material ---------------------------------------------------------


async def test_related_material_must_be_owned(client: AsyncClient) -> None:
    owner, stranger = await dev_login(client, "Анна"), await dev_login(client, "Борис")
    material = await _create_material(client, owner)

    ok = await client.post(
        f"{API}/assignments",
        json={**ASSIGNMENT, "related_material_id": material["id"]},
        headers=owner,
    )
    assert ok.status_code == 201
    assert ok.json()["related_material_id"] == material["id"]

    # A foreign material id is a body problem (422), not a resource miss.
    linked_foreign = await client.post(
        f"{API}/assignments",
        json={**ASSIGNMENT, "related_material_id": material["id"]},
        headers=stranger,
    )
    assert linked_foreign.status_code == 422

    # Same rule on update; unlinking with null is allowed.
    updated = await client.patch(
        f"{API}/assignments/{ok.json()['id']}",
        json={"related_material_id": None},
        headers=owner,
    )
    assert updated.status_code == 200
    assert updated.json()["related_material_id"] is None


async def test_material_deletion_unlinks_assignment(client: AsyncClient) -> None:
    headers = await dev_login(client)
    material = await _create_material(client, headers)
    assignment = await _create(client, headers, related_material_id=material["id"])

    deleted = await client.delete(f"{API}/materials/{material['id']}", headers=headers)
    assert deleted.status_code == 204

    fetched = await client.get(
        f"{API}/assignments/{assignment['id']}", headers=headers
    )
    assert fetched.status_code == 200
    assert fetched.json()["related_material_id"] is None


# --- filtering / ordering -----------------------------------------------------


async def test_active_with_nearest_deadline_lists_first(client: AsyncClient) -> None:
    headers = await dev_login(client)
    soon = (datetime.now(UTC) + timedelta(days=1)).isoformat()
    far = (datetime.now(UTC) + timedelta(days=10)).isoformat()

    await _create(client, headers, title="Далекое", due_at=far)
    await _create(client, headers, title="Ближнее", due_at=soon)
    await _create(client, headers, title="Без срока", due_at=None)

    listed = await client.get(f"{API}/assignments", headers=headers)
    titles = [a["title"] for a in listed.json()["items"]]
    assert titles[:2] == ["Ближнее", "Далекое"]


async def test_filter_by_status_class_and_search(client: AsyncClient) -> None:
    headers = await dev_login(client)
    await _create(client, headers, title="Диктант", class_name="6А", status="done")
    await _create(client, headers, title="Реферат", class_name="7Б")

    done_only = await client.get(f"{API}/assignments?status=done", headers=headers)
    assert [a["title"] for a in done_only.json()["items"]] == ["Диктант"]

    by_class = await client.get(f"{API}/assignments?class_name=7Б", headers=headers)
    assert [a["title"] for a in by_class.json()["items"]] == ["Реферат"]

    by_search = await client.get(f"{API}/assignments?search=реферат", headers=headers)
    assert [a["title"] for a in by_search.json()["items"]] == ["Реферат"]


async def test_unknown_status_filter_is_empty_not_error(client: AsyncClient) -> None:
    headers = await dev_login(client)
    await _create(client, headers)
    response = await client.get(f"{API}/assignments?status=нелепый", headers=headers)
    assert response.status_code == 200
    assert response.json()["total"] == 0


# --- ownership (IDOR) ---------------------------------------------------------


async def test_foreign_assignment_invisible_by_id(client: AsyncClient) -> None:
    owner, stranger = await dev_login(client, "Анна"), await dev_login(client, "Борис")
    assignment = await _create(client, owner)

    read = await client.get(f"{API}/assignments/{assignment['id']}", headers=stranger)
    assert read.status_code == 404

    patch = await client.patch(
        f"{API}/assignments/{assignment['id']}",
        json={"status": "done"},
        headers=stranger,
    )
    assert patch.status_code == 404

    delete = await client.delete(
        f"{API}/assignments/{assignment['id']}", headers=stranger
    )
    assert delete.status_code == 404

    # The owner still sees the assignment untouched.
    original = await client.get(f"{API}/assignments/{assignment['id']}", headers=owner)
    assert original.json()["status"] == "active"


async def test_missing_assignment_is_404(client: AsyncClient) -> None:
    headers = await dev_login(client)
    response = await client.get(f"{API}/assignments/{uuid.uuid4()}", headers=headers)
    assert response.status_code == 404


async def test_malformed_id_returns_422(client: AsyncClient) -> None:
    headers = await dev_login(client)
    response = await client.get(f"{API}/assignments/not-a-uuid", headers=headers)
    assert response.status_code == 422


# --- validation ---------------------------------------------------------------


async def test_blank_title_rejected(client: AsyncClient) -> None:
    headers = await dev_login(client)
    for title in ("", "   "):
        response = await client.post(
            f"{API}/assignments", json={**ASSIGNMENT, "title": title}, headers=headers
        )
        assert response.status_code == 422


async def test_unknown_status_value_rejected(client: AsyncClient) -> None:
    headers = await dev_login(client)
    response = await client.post(
        f"{API}/assignments", json={**ASSIGNMENT, "status": "cancelled"}, headers=headers
    )
    assert response.status_code == 422


async def test_unknown_field_rejected(client: AsyncClient) -> None:
    headers = await dev_login(client)
    response = await client.post(
        f"{API}/assignments",
        json={**ASSIGNMENT, "owner_id": "00000000-0000-0000-0000-000000000000"},
        headers=headers,
    )
    assert response.status_code == 422


async def test_invalid_due_at_rejected(client: AsyncClient) -> None:
    headers = await dev_login(client)
    response = await client.post(
        f"{API}/assignments",
        json={**ASSIGNMENT, "due_at": "не дата"},
        headers=headers,
    )
    assert response.status_code == 422


async def test_too_long_description_rejected(client: AsyncClient) -> None:
    headers = await dev_login(client)
    response = await client.post(
        f"{API}/assignments",
        json={**ASSIGNMENT, "description": "д" * 5001},
        headers=headers,
    )
    assert response.status_code == 422

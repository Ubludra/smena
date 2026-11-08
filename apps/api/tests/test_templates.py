"""Templates API: per-type payload validation, filtering, ownership.

The core guarantee: a template's payload is validated with the *same* schema
the target entity's create endpoint uses, so «use template» can never
produce an entity the API would reject.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from helpers import dev_login

if TYPE_CHECKING:
    from httpx import AsyncClient

API = "/api/v1"

PLAN_TEMPLATE = {
    "name": "Шаблон: стандартный урок",
    "entity_type": "lesson_plan",
    "payload": {
        "title": "Урок по шаблону",
        "subject": "Математика",
        "class_name": "7Б",
        "duration_minutes": 45,
        "objectives": ["Повторить", "Закрепить"],
        "stages": [
            {"title": "Разминка", "minutes": 5, "description": "Опрос"},
            {"title": "Практика", "minutes": 30, "description": ""},
        ],
    },
}

ASSIGNMENT_TEMPLATE = {
    "name": "Шаблон: домашка",
    "entity_type": "assignment",
    "payload": {
        "title": "Домашнее задание",
        "description": "Параграф, упражнения",
        "status": "active",
    },
}


async def _create(client: AsyncClient, headers: dict[str, str], **overrides) -> dict:
    payload = {**PLAN_TEMPLATE, **overrides}
    response = await client.post(f"{API}/templates", json=payload, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


# --- authentication -----------------------------------------------------------


async def test_list_requires_auth(client: AsyncClient) -> None:
    response = await client.get(f"{API}/templates")
    assert response.status_code == 401


async def test_new_teacher_sees_only_builtins(client: AsyncClient) -> None:
    """No personal rows; the seeded system skeletons are visible, flagged."""
    headers = await dev_login(client)
    response = await client.get(f"{API}/templates", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["total"] > 0
    assert all(item["is_system"] for item in body["items"])


# --- CRUD happy path ----------------------------------------------------------


async def test_create_read_update_delete(client: AsyncClient) -> None:
    headers = await dev_login(client)
    template = await _create(client, headers)
    template_id = template["id"]

    assert template["entity_type"] == "lesson_plan"
    assert template["payload"]["title"] == "Урок по шаблону"

    fetched = await client.get(f"{API}/templates/{template_id}", headers=headers)
    assert fetched.status_code == 200
    assert fetched.json()["name"] == "Шаблон: стандартный урок"

    renamed = await client.patch(
        f"{API}/templates/{template_id}",
        json={"name": "Шаблон: урок с практикой"},
        headers=headers,
    )
    assert renamed.status_code == 200
    assert renamed.json()["name"] == "Шаблон: урок с практикой"
    # Payload untouched by a name-only patch.
    assert renamed.json()["payload"]["title"] == "Урок по шаблону"

    deleted = await client.delete(f"{API}/templates/{template_id}", headers=headers)
    assert deleted.status_code == 204
    after = await client.get(f"{API}/templates/{template_id}", headers=headers)
    assert after.status_code == 404


# --- payload validation (never trust client JSON) ------------------------------


async def test_invalid_payload_rejected(client: AsyncClient) -> None:
    headers = await dev_login(client)
    # Blank title in a lesson_plan payload — the create schema rejects it.
    response = await client.post(
        f"{API}/templates",
        json={
            "name": "Плохой шаблон",
            "entity_type": "lesson_plan",
            "payload": {"title": "   "},
        },
        headers=headers,
    )
    assert response.status_code == 422


async def test_payload_rejected_for_wrong_type(client: AsyncClient) -> None:
    headers = await dev_login(client)
    # Assignment payload under the lesson_plan type: title-only is fine for a
    # plan, but "status" is unknown to LessonPlanCreate → rejected.
    response = await client.post(
        f"{API}/templates",
        json={
            "name": "Смешанный шаблон",
            "entity_type": "lesson_plan",
            "payload": {**ASSIGNMENT_TEMPLATE["payload"]},
        },
        headers=headers,
    )
    assert response.status_code == 422


async def test_unknown_entity_type_rejected(client: AsyncClient) -> None:
    headers = await dev_login(client)
    response = await client.post(
        f"{API}/templates",
        json={
            "name": "Странный шаблон",
            "entity_type": "presentation",
            "payload": {"title": "x"},
        },
        headers=headers,
    )
    assert response.status_code == 422


async def test_unknown_field_in_payload_rejected(client: AsyncClient) -> None:
    headers = await dev_login(client)
    response = await client.post(
        f"{API}/templates",
        json={
            **PLAN_TEMPLATE,
            "payload": {**PLAN_TEMPLATE["payload"], "owner_id": "hack"},
        },
        headers=headers,
    )
    assert response.status_code == 422


async def test_payload_revalidated_on_update(client: AsyncClient) -> None:
    headers = await dev_login(client)
    template = await _create(client, headers)

    bad_update = await client.patch(
        f"{API}/templates/{template['id']}",
        json={"payload": {"title": ""}},
        headers=headers,
    )
    assert bad_update.status_code == 422

    good_update = await client.patch(
        f"{API}/templates/{template['id']}",
        json={"payload": {**PLAN_TEMPLATE["payload"], "topic": "обновлено"}},
        headers=headers,
    )
    assert good_update.status_code == 200
    assert good_update.json()["payload"]["topic"] == "обновлено"


# --- filtering ----------------------------------------------------------------


async def test_filter_by_entity_type(client: AsyncClient) -> None:
    headers = await dev_login(client)
    await _create(client, headers)
    await client.post(
        f"{API}/templates", json=ASSIGNMENT_TEMPLATE, headers=headers
    )

    plans = await client.get(
        f"{API}/templates?entity_type=lesson_plan", headers=headers
    )
    assert [t["name"] for t in plans.json()["items"]] == ["Шаблон: стандартный урок"]

    assignments = await client.get(
        f"{API}/templates?entity_type=assignment", headers=headers
    )
    assert [t["name"] for t in assignments.json()["items"]] == ["Шаблон: домашка"]


# --- ownership (IDOR) ---------------------------------------------------------


async def test_foreign_template_invisible_by_id(client: AsyncClient) -> None:
    owner, stranger = await dev_login(client, "Анна"), await dev_login(client, "Борис")
    template = await _create(client, owner)

    read = await client.get(f"{API}/templates/{template['id']}", headers=stranger)
    assert read.status_code == 404

    patch = await client.patch(
        f"{API}/templates/{template['id']}",
        json={"name": "взлом"},
        headers=stranger,
    )
    assert patch.status_code == 404

    delete = await client.delete(f"{API}/templates/{template['id']}", headers=stranger)
    assert delete.status_code == 404

    # The owner still sees the template untouched.
    original = await client.get(f"{API}/templates/{template['id']}", headers=owner)
    assert original.json()["name"] == "Шаблон: стандартный урок"


async def test_missing_template_is_404(client: AsyncClient) -> None:
    headers = await dev_login(client)
    response = await client.get(f"{API}/templates/{uuid.uuid4()}", headers=headers)
    assert response.status_code == 404


async def test_malformed_id_returns_422(client: AsyncClient) -> None:
    headers = await dev_login(client)
    response = await client.get(f"{API}/templates/not-a-uuid", headers=headers)
    assert response.status_code == 422


# --- validation ---------------------------------------------------------------


async def test_blank_name_rejected(client: AsyncClient) -> None:
    headers = await dev_login(client)
    for name in ("", "   "):
        response = await client.post(
            f"{API}/templates", json={**PLAN_TEMPLATE, "name": name}, headers=headers
        )
        assert response.status_code == 422


async def test_unknown_field_rejected(client: AsyncClient) -> None:
    headers = await dev_login(client)
    response = await client.post(
        f"{API}/templates",
        json={**PLAN_TEMPLATE, "owner_id": "00000000-0000-0000-0000-000000000000"},
        headers=headers,
    )
    assert response.status_code == 422


# --- built-in system report templates ------------------------------------------


async def _report_ids(client: AsyncClient, headers: dict[str, str]) -> list[dict]:
    response = await client.get(
        f"{API}/templates", params={"entity_type": "report"}, headers=headers
    )
    assert response.status_code == 200, response.text
    return response.json()["items"]


async def test_seeded_report_templates_visible_to_every_user(
    client: AsyncClient,
) -> None:
    from smena_api.services.builtin_reports import BUILTIN_REPORT_TEMPLATES

    anna, boris = await dev_login(client, "Анна"), await dev_login(client, "Борис")
    for headers in (anna, boris):
        items = await _report_ids(client, headers)
        names = {item["name"] for item in items}
        expected = {row["name"] for row in BUILTIN_REPORT_TEMPLATES}
        assert expected <= names
        assert all(item["is_system"] for item in items)


async def test_report_payloads_are_valid_material_creates(client: AsyncClient) -> None:
    """«Use template» feeds the material form: every skeleton must pass the
    exact schema the materials POST enforces."""
    from smena_api.schemas.material import MaterialCreate

    headers = await dev_login(client)
    for item in await _report_ids(client, headers):
        material = MaterialCreate.model_validate(item["payload"])
        assert len(material.content) > 500  # a real skeleton, not a stub


async def test_system_template_readable_by_id(client: AsyncClient) -> None:
    anna, boris = await dev_login(client, "Анна"), await dev_login(client, "Борис")
    items = await _report_ids(client, anna)
    first = items[0]
    shared = await client.get(f"{API}/templates/{first['id']}", headers=boris)
    assert shared.status_code == 200
    assert shared.json()["is_system"] is True


async def test_system_templates_are_read_only(client: AsyncClient) -> None:
    """PATCH/DELETE answer the same 404 as a foreign row — read-only without
    advertising that the id exists at all."""
    headers = await dev_login(client)
    items = await _report_ids(client, headers)
    first = items[0]

    patch = await client.patch(
        f"{API}/templates/{first['id']}", json={"name": "Взлом"}, headers=headers
    )
    assert patch.status_code == 404

    delete = await client.delete(f"{API}/templates/{first['id']}", headers=headers)
    assert delete.status_code == 404

    still = await client.get(f"{API}/templates/{first['id']}", headers=headers)
    assert still.status_code == 200 and still.json()["name"] == first["name"]


async def test_client_cannot_create_report_type_template(client: AsyncClient) -> None:
    headers = await dev_login(client)
    response = await client.post(
        f"{API}/templates",
        json={
            "name": "Мой отчёт",
            "entity_type": "report",
            "payload": {"title": "Что-то"},
        },
        headers=headers,
    )
    assert response.status_code == 422


async def test_client_cannot_retype_own_template_to_report(client: AsyncClient) -> None:
    headers = await dev_login(client)
    own = await _create(client, headers)
    response = await client.patch(
        f"{API}/templates/{own['id']}", json={"entity_type": "report"}, headers=headers
    )
    assert response.status_code == 422


async def test_user_templates_keep_is_system_false(client: AsyncClient) -> None:
    headers = await dev_login(client)
    own = await _create(client, headers)
    assert own["is_system"] is False

"""Lesson plans API: CRUD, filtering, duplicate, ownership (IDOR), validation.

Same guarantees as materials: ownership is enforced in the service layer,
foreign and missing ids both answer 404 (no existence oracle), and no field
is accepted without server-side validation.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from helpers import dev_login

if TYPE_CHECKING:
    from httpx import AsyncClient

API = "/api/v1"

PLAN = {
    "title": "Урок: падежи",
    "subject": "Русский язык",
    "class_name": "6А",
    "lesson_date": "2026-11-05",
    "start_time": "09:00:00",
    "duration_minutes": 45,
    "topic": "Именительный и винительный падежи",
    "goal": "Различать падежи",
    "objectives": ["Знать вопросы падежей", "Уметь склонять"],
    "stages": [
        {"title": "Разминка", "minutes": 5, "description": "Фронтальный опрос"},
        {"title": "Практика", "minutes": 30, "description": "Карточки"},
    ],
    "homework": "Упр. 120",
    "notes": "Проектор нужен",
}


async def _create(client: AsyncClient, headers: dict[str, str], **overrides) -> dict:
    payload = {**PLAN, **overrides}
    response = await client.post(f"{API}/lesson-plans", json=payload, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


# --- authentication -----------------------------------------------------------


async def test_list_requires_auth(client: AsyncClient) -> None:
    response = await client.get(f"{API}/lesson-plans")
    assert response.status_code == 401


async def test_empty_list_for_new_teacher(client: AsyncClient) -> None:
    headers = await dev_login(client)
    response = await client.get(f"{API}/lesson-plans", headers=headers)
    assert response.status_code == 200
    assert response.json() == {"items": [], "total": 0}


# --- CRUD happy path ----------------------------------------------------------


async def test_create_read_update_delete(client: AsyncClient) -> None:
    headers = await dev_login(client)
    plan = await _create(client, headers)
    plan_id = plan["id"]

    first_stage = {"title": "Разминка", "minutes": 5, "description": "Фронтальный опрос"}
    assert plan["stages"][0] == first_stage
    assert plan["objectives"] == ["Знать вопросы падежей", "Уметь склонять"]

    fetched = await client.get(f"{API}/lesson-plans/{plan_id}", headers=headers)
    assert fetched.status_code == 200
    assert fetched.json()["topic"] == "Именительный и винительный падежи"

    patched = await client.patch(
        f"{API}/lesson-plans/{plan_id}",
        json={"topic": "Родительный падеж", "duration_minutes": 40},
        headers=headers,
    )
    assert patched.status_code == 200
    assert patched.json()["topic"] == "Родительный падеж"
    assert patched.json()["duration_minutes"] == 40
    # Untouched fields survive a partial update.
    assert patched.json()["stages"][0]["title"] == "Разминка"

    deleted = await client.delete(f"{API}/lesson-plans/{plan_id}", headers=headers)
    assert deleted.status_code == 204
    after = await client.get(f"{API}/lesson-plans/{plan_id}", headers=headers)
    assert after.status_code == 404


# --- duplicate ----------------------------------------------------------------


async def test_duplicate_copies_content_and_ownership(client: AsyncClient) -> None:
    headers = await dev_login(client)
    plan = await _create(client, headers)

    copied = await client.post(f"{API}/lesson-plans/{plan['id']}/duplicate", headers=headers)
    assert copied.status_code == 201
    copy = copied.json()
    assert copy["id"] != plan["id"]
    assert copy["title"] == "Урок: падежи (копия)"
    assert copy["stages"] == plan["stages"]
    assert copy["objectives"] == plan["objectives"]
    assert copy["homework"] == plan["homework"]

    # Editing the copy never touches the original.
    await client.patch(
        f"{API}/lesson-plans/{copy['id']}", json={"topic": "изменено"}, headers=headers
    )
    original = await client.get(f"{API}/lesson-plans/{plan['id']}", headers=headers)
    assert original.json()["topic"] == "Именительный и винительный падежи"


async def test_duplicate_long_title_is_truncated(client: AsyncClient) -> None:
    headers = await dev_login(client)
    plan = await _create(client, headers, title="У" * 200)
    copied = await client.post(f"{API}/lesson-plans/{plan['id']}/duplicate", headers=headers)
    assert copied.status_code == 201
    assert len(copied.json()["title"]) == 200
    assert copied.json()["title"].endswith(" (копия)")


async def test_duplicate_foreign_plan_is_404(client: AsyncClient) -> None:
    owner, stranger = await dev_login(client, "Анна"), await dev_login(client, "Борис")
    plan = await _create(client, owner)
    response = await client.post(
        f"{API}/lesson-plans/{plan['id']}/duplicate", headers=stranger
    )
    assert response.status_code == 404


# --- filtering ----------------------------------------------------------------


async def test_search_matches_title_and_topic(client: AsyncClient) -> None:
    headers = await dev_login(client)
    await _create(client, headers, title="Диктант", topic="Правописание приставок")
    await _create(client, headers, title="Обычный урок", topic="Сложение дробей")

    by_title = await client.get(f"{API}/lesson-plans?search=диктант", headers=headers)
    assert [p["title"] for p in by_title.json()["items"]] == ["Диктант"]
    by_topic = await client.get(f"{API}/lesson-plans?search=дробей", headers=headers)
    assert [p["title"] for p in by_topic.json()["items"]] == ["Обычный урок"]


async def test_filters_by_class_subject_and_date(client: AsyncClient) -> None:
    headers = await dev_login(client)
    await _create(client, headers, title="A", class_name="6А", subject="Русский язык",
                  lesson_date="2026-11-05")
    await _create(client, headers, title="B", class_name="7Б", subject="Математика",
                  lesson_date="2026-11-06")
    await _create(client, headers, title="C", class_name="6А", subject="Русский язык",
                  lesson_date="2026-12-01")

    by_class = await client.get(f"{API}/lesson-plans?class_name=6А", headers=headers)
    assert sorted(p["title"] for p in by_class.json()["items"]) == ["A", "C"]

    by_subject = await client.get(f"{API}/lesson-plans?subject=математика", headers=headers)
    assert [p["title"] for p in by_subject.json()["items"]] == ["B"]

    by_range = await client.get(
        f"{API}/lesson-plans?date_from=2026-11-05&date_to=2026-11-30", headers=headers
    )
    assert sorted(p["title"] for p in by_range.json()["items"]) == ["A", "B"]


async def test_pagination(client: AsyncClient) -> None:
    headers = await dev_login(client)
    for i in range(3):
        await _create(client, headers, title=f"План {i}")
    page = await client.get(f"{API}/lesson-plans?limit=2&offset=0", headers=headers)
    body = page.json()
    assert body["total"] == 3
    assert len(body["items"]) == 2
    second = await client.get(f"{API}/lesson-plans?limit=2&offset=2", headers=headers)
    assert len(second.json()["items"]) == 1


# --- ownership (IDOR) ---------------------------------------------------------


async def test_foreign_plan_invisible_by_id(client: AsyncClient) -> None:
    owner, stranger = await dev_login(client, "Анна"), await dev_login(client, "Борис")
    plan = await _create(client, owner)

    read = await client.get(f"{API}/lesson-plans/{plan['id']}", headers=stranger)
    assert read.status_code == 404

    patch = await client.patch(
        f"{API}/lesson-plans/{plan['id']}", json={"title": "взлом"}, headers=stranger
    )
    assert patch.status_code == 404

    delete = await client.delete(f"{API}/lesson-plans/{plan['id']}", headers=stranger)
    assert delete.status_code == 404

    # The owner still sees the plan untouched.
    original = await client.get(f"{API}/lesson-plans/{plan['id']}", headers=owner)
    assert original.json()["title"] == "Урок: падежи"


async def test_missing_plan_is_404(client: AsyncClient) -> None:
    headers = await dev_login(client)
    response = await client.get(f"{API}/lesson-plans/{uuid.uuid4()}", headers=headers)
    assert response.status_code == 404


async def test_malformed_id_returns_422(client: AsyncClient) -> None:
    headers = await dev_login(client)
    response = await client.get(f"{API}/lesson-plans/not-a-uuid", headers=headers)
    assert response.status_code == 422


# --- validation ---------------------------------------------------------------


async def test_blank_title_rejected(client: AsyncClient) -> None:
    headers = await dev_login(client)
    for title in ("", "   "):
        response = await client.post(
            f"{API}/lesson-plans", json={**PLAN, "title": title}, headers=headers
        )
        assert response.status_code == 422


async def test_too_long_title_rejected(client: AsyncClient) -> None:
    headers = await dev_login(client)
    response = await client.post(
        f"{API}/lesson-plans", json={**PLAN, "title": "У" * 201}, headers=headers
    )
    assert response.status_code == 422


async def test_bad_duration_rejected(client: AsyncClient) -> None:
    headers = await dev_login(client)
    for minutes in (0, -10, 601):
        response = await client.post(
            f"{API}/lesson-plans", json={**PLAN, "duration_minutes": minutes}, headers=headers
        )
        assert response.status_code == 422, minutes


async def test_stage_validation(client: AsyncClient) -> None:
    headers = await dev_login(client)
    # A stage without a title is rejected.
    response = await client.post(
        f"{API}/lesson-plans", json={**PLAN, "stages": [{"minutes": 5}]}, headers=headers
    )
    assert response.status_code == 422
    # Extra keys inside a stage are rejected, not silently dropped.
    response = await client.post(
        f"{API}/lesson-plans",
        json={**PLAN, "stages": [{"title": "Этап", "hacker": True}]},
        headers=headers,
    )
    assert response.status_code == 422


async def test_unknown_field_rejected(client: AsyncClient) -> None:
    headers = await dev_login(client)
    response = await client.post(
        f"{API}/lesson-plans", json={**PLAN, "owner_id": "00000000-0000-0000-0000-000000000000"},
        headers=headers,
    )
    assert response.status_code == 422
    # owner_id from the client is never an identity source: the created plan
    # belongs to the token's user regardless of any submitted field.
    await _create(client, headers)


async def test_invalid_date_rejected(client: AsyncClient) -> None:
    headers = await dev_login(client)
    response = await client.post(
        f"{API}/lesson-plans", json={**PLAN, "lesson_date": "2026-13-45"}, headers=headers
    )
    assert response.status_code == 422


async def test_too_many_objectives_rejected(client: AsyncClient) -> None:
    headers = await dev_login(client)
    response = await client.post(
        f"{API}/lesson-plans", json={**PLAN, "objectives": ["цель"] * 21}, headers=headers
    )
    assert response.status_code == 422

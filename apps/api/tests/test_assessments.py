"""Assessments API: CRUD with questions, duplicate, Safe flag, ownership.

The answer key is part of the teacher's content; question payloads are
validated server-side (type rules, option indexes) so arbitrary JSON never
reaches the ORM. Ownership: foreign ids answer 404 like every other module.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from helpers import dev_login, unlock_safe

if TYPE_CHECKING:
    from httpx import AsyncClient

API = "/api/v1"

QUESTIONS = [
    {
        "text": "В каком году началась Вторая мировая война?",
        "type": "single",
        "options": ["1939", "1941", "1945"],
        "correct": [0],
    },
    {
        "text": "Выберите страны-участницы антигитлеровской коалиции",
        "type": "multi",
        "options": ["СССР", "Германия", "США", "Италия"],
        "correct": [0, 2],
    },
    {
        "text": "Назовите столицу СССР",
        "type": "text",
        "options": [],
        "correct": ["Москва"],
    },
]

ASSESSMENT = {
    "title": "Контрольная по истории, 8А",
    "description": "Итоговая работа по теме Второй мировой войны",
    "subject": "История",
    "class_name": "8А",
    "duration_minutes": 45,
    "questions": QUESTIONS,
}


async def _create(client: AsyncClient, headers: dict[str, str], **overrides) -> dict:
    payload = {**ASSESSMENT, **overrides}
    response = await client.post(f"{API}/assessments", json=payload, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


# --- authentication -----------------------------------------------------------


async def test_list_requires_auth(client: AsyncClient) -> None:
    response = await client.get(f"{API}/assessments")
    assert response.status_code == 401


async def test_empty_list_for_new_teacher(client: AsyncClient) -> None:
    headers = await dev_login(client)
    response = await client.get(f"{API}/assessments", headers=headers)
    assert response.status_code == 200
    assert response.json() == {"items": [], "total": 0}


# --- CRUD happy path ----------------------------------------------------------


async def test_create_read_update_delete(client: AsyncClient) -> None:
    headers = await dev_login(client)
    assessment = await _create(client, headers)
    assessment_id = assessment["id"]

    assert len(assessment["questions"]) == 3
    # Questions arrive in submission order.
    assert assessment["questions"][0]["text"] == QUESTIONS[0]["text"]
    assert assessment["questions"][2]["correct"] == ["Москва"]

    fetched = await client.get(f"{API}/assessments/{assessment_id}", headers=headers)
    assert fetched.status_code == 200
    assert fetched.json()["title"] == "Контрольная по истории, 8А"

    # Replace the question set and flip the Safe flag in one PATCH.
    patched = await client.patch(
        f"{API}/assessments/{assessment_id}",
        json={
            "title": "Контрольная по истории, 8Б",
            "is_protected": True,
            "questions": QUESTIONS[:1],
        },
        headers=headers,
    )
    assert patched.status_code == 200
    assert patched.json()["title"] == "Контрольная по истории, 8Б"
    assert patched.json()["is_protected"] is True
    assert len(patched.json()["questions"]) == 1

    # Untouched fields survive the partial update.
    assert patched.json()["duration_minutes"] == 45

    deleted = await client.delete(f"{API}/assessments/{assessment_id}", headers=headers)
    assert deleted.status_code == 204
    after = await client.get(f"{API}/assessments/{assessment_id}", headers=headers)
    assert after.status_code == 404


async def test_update_without_questions_keeps_them(client: AsyncClient) -> None:
    headers = await dev_login(client)
    assessment = await _create(client, headers)
    patched = await client.patch(
        f"{API}/assessments/{assessment['id']}",
        json={"description": "перенесена на пятницу"},
        headers=headers,
    )
    assert patched.status_code == 200
    assert len(patched.json()["questions"]) == 3


async def test_toggle_safe_flag(client: AsyncClient) -> None:
    headers = await unlock_safe(client, await dev_login(client))
    assessment = await _create(client, headers)

    listed = await client.get(f"{API}/assessments?only_protected=true", headers=headers)
    assert listed.json()["total"] == 0

    await client.patch(
        f"{API}/assessments/{assessment['id']}",
        json={"is_protected": True},
        headers=headers,
    )
    listed = await client.get(f"{API}/assessments?only_protected=true", headers=headers)
    assert [a["id"] for a in listed.json()["items"]] == [assessment["id"]]


# --- duplicate ----------------------------------------------------------------


async def test_duplicate_copies_questions(client: AsyncClient) -> None:
    headers = await dev_login(client)
    assessment = await _create(client, headers)

    copied = await client.post(
        f"{API}/assessments/{assessment['id']}/duplicate", headers=headers
    )
    assert copied.status_code == 201
    copy = copied.json()
    assert copy["id"] != assessment["id"]
    assert copy["title"] == "Контрольная по истории, 8А (копия)"
    # Same content, new rows: compare without row ids.
    def strip_ids(questions: list[dict]) -> list[dict]:
        return [{k: v for k, v in q.items() if k != "id"} for q in questions]

    assert strip_ids(copy["questions"]) == strip_ids(assessment["questions"])
    assert copy["is_protected"] == assessment["is_protected"]

    # Editing the copy never touches the original.
    await client.patch(
        f"{API}/assessments/{copy['id']}",
        json={"title": "изменено"},
        headers=headers,
    )
    original = await client.get(f"{API}/assessments/{assessment['id']}", headers=headers)
    assert original.json()["title"] == "Контрольная по истории, 8А"


async def test_duplicate_foreign_assessment_is_404(client: AsyncClient) -> None:
    owner, stranger = await dev_login(client, "Анна"), await dev_login(client, "Борис")
    assessment = await _create(client, owner)
    response = await client.post(
        f"{API}/assessments/{assessment['id']}/duplicate", headers=stranger
    )
    assert response.status_code == 404


# --- filtering ----------------------------------------------------------------


async def test_search_and_filters(client: AsyncClient) -> None:
    headers = await dev_login(client)
    await _create(client, headers, title="Диктант", class_name="8А", subject="История")
    await _create(client, headers, title="Тест по дробям", class_name="7Б", subject="Математика")

    by_search = await client.get(f"{API}/assessments?search=дробям", headers=headers)
    assert [a["title"] for a in by_search.json()["items"]] == ["Тест по дробям"]

    by_class = await client.get(f"{API}/assessments?class_name=8А", headers=headers)
    assert [a["title"] for a in by_class.json()["items"]] == ["Диктант"]

    by_subject = await client.get(f"{API}/assessments?subject=история", headers=headers)
    assert [a["title"] for a in by_subject.json()["items"]] == ["Диктант"]


async def test_pagination(client: AsyncClient) -> None:
    headers = await dev_login(client)
    for i in range(3):
        await _create(client, headers, title=f"Проверочная {i}")
    page = await client.get(f"{API}/assessments?limit=2&offset=0", headers=headers)
    body = page.json()
    assert body["total"] == 3
    assert len(body["items"]) == 2
    second = await client.get(f"{API}/assessments?limit=2&offset=2", headers=headers)
    assert len(second.json()["items"]) == 1


# --- ownership (IDOR) ---------------------------------------------------------


async def test_foreign_assessment_invisible_by_id(client: AsyncClient) -> None:
    owner, stranger = await dev_login(client, "Анна"), await dev_login(client, "Борис")
    assessment = await _create(client, owner)

    read = await client.get(f"{API}/assessments/{assessment['id']}", headers=stranger)
    assert read.status_code == 404

    patch = await client.patch(
        f"{API}/assessments/{assessment['id']}",
        json={"title": "взлом"},
        headers=stranger,
    )
    assert patch.status_code == 404

    delete = await client.delete(
        f"{API}/assessments/{assessment['id']}", headers=stranger
    )
    assert delete.status_code == 404

    # The owner still sees the assessment untouched, answer keys included.
    original = await client.get(f"{API}/assessments/{assessment['id']}", headers=owner)
    assert original.json()["title"] == "Контрольная по истории, 8А"


async def test_missing_assessment_is_404(client: AsyncClient) -> None:
    headers = await dev_login(client)
    response = await client.get(f"{API}/assessments/{uuid.uuid4()}", headers=headers)
    assert response.status_code == 404


async def test_malformed_id_returns_422(client: AsyncClient) -> None:
    headers = await dev_login(client)
    response = await client.get(f"{API}/assessments/not-a-uuid", headers=headers)
    assert response.status_code == 422


# --- validation ---------------------------------------------------------------


async def test_blank_title_rejected(client: AsyncClient) -> None:
    headers = await dev_login(client)
    for title in ("", "   "):
        response = await client.post(
            f"{API}/assessments", json={**ASSESSMENT, "title": title}, headers=headers
        )
        assert response.status_code == 422


async def test_choice_question_needs_options_and_valid_key(client: AsyncClient) -> None:
    headers = await dev_login(client)

    too_few_options = await client.post(
        f"{API}/assessments",
        json={
            **ASSESSMENT,
            "questions": [
                {"text": "Вопрос?", "type": "single", "options": ["один"], "correct": [0]}
            ],
        },
        headers=headers,
    )
    assert too_few_options.status_code == 422

    key_out_of_range = await client.post(
        f"{API}/assessments",
        json={
            **ASSESSMENT,
            "questions": [
                {
                    "text": "Вопрос?",
                    "type": "single",
                    "options": ["а", "б"],
                    "correct": [5],
                }
            ],
        },
        headers=headers,
    )
    assert key_out_of_range.status_code == 422

    no_key = await client.post(
        f"{API}/assessments",
        json={
            **ASSESSMENT,
            "questions": [{"text": "Вопрос?", "type": "multi", "options": ["а", "б"]}],
        },
        headers=headers,
    )
    assert no_key.status_code == 422

    single_needs_one_key = await client.post(
        f"{API}/assessments",
        json={
            **ASSESSMENT,
            "questions": [
                {
                    "text": "Вопрос?",
                    "type": "single",
                    "options": ["а", "б"],
                    "correct": [0, 1],
                }
            ],
        },
        headers=headers,
    )
    assert single_needs_one_key.status_code == 422


async def test_text_question_rules(client: AsyncClient) -> None:
    headers = await dev_login(client)

    with_options = await client.post(
        f"{API}/assessments",
        json={
            **ASSESSMENT,
            "questions": [
                {
                    "text": "Вопрос?",
                    "type": "text",
                    "options": ["лишний"],
                    "correct": ["ответ"],
                }
            ],
        },
        headers=headers,
    )
    assert with_options.status_code == 422

    without_key = await client.post(
        f"{API}/assessments",
        json={**ASSESSMENT, "questions": [{"text": "Вопрос?", "type": "text"}]},
        headers=headers,
    )
    assert without_key.status_code == 422


async def test_unknown_question_type_rejected(client: AsyncClient) -> None:
    headers = await dev_login(client)
    response = await client.post(
        f"{API}/assessments",
        json={
            **ASSESSMENT,
            "questions": [
                {
                    "text": "Вопрос?",
                    "type": "matching",
                    "options": ["а", "б"],
                    "correct": [0],
                }
            ],
        },
        headers=headers,
    )
    assert response.status_code == 422


async def test_unknown_field_rejected(client: AsyncClient) -> None:
    headers = await dev_login(client)
    response = await client.post(
        f"{API}/assessments",
        json={**ASSESSMENT, "owner_id": "00000000-0000-0000-0000-000000000000"},
        headers=headers,
    )
    assert response.status_code == 422


async def test_bad_duration_rejected(client: AsyncClient) -> None:
    headers = await dev_login(client)
    for minutes in (0, -5, 601):
        response = await client.post(
            f"{API}/assessments",
            json={**ASSESSMENT, "duration_minutes": minutes},
            headers=headers,
        )
        assert response.status_code == 422, minutes

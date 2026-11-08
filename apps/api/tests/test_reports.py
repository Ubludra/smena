"""Reports API: real aggregates only, ownership-scoped, honest periods.

The report must contain exactly what the fixtures put into the DB — no more,
no less. Invented performance metrics are impossible by construction: the
schemas have no fields for them.
"""

from __future__ import annotations

import datetime as dt
from typing import TYPE_CHECKING

from helpers import dev_login

if TYPE_CHECKING:
    from httpx import AsyncClient

API = "/api/v1"


async def _create_plan(
    client: AsyncClient, headers: dict[str, str], **overrides
) -> dict:
    payload = {
        "title": overrides.pop("title", "План"),
        "lesson_date": overrides.pop("lesson_date", None),
        **overrides,
    }
    response = await client.post(f"{API}/lesson-plans", json=payload, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


async def _create_assignment(
    client: AsyncClient, headers: dict[str, str], **overrides
) -> dict:
    payload = {
        "title": overrides.pop("title", "Задание"),
        "due_at": overrides.pop("due_at", None),
        **overrides,
    }
    response = await client.post(f"{API}/assignments", json=payload, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


# --- authentication -----------------------------------------------------------


async def test_summary_requires_auth(client: AsyncClient) -> None:
    response = await client.get(f"{API}/reports/summary")
    assert response.status_code == 401


# --- aggregation ---------------------------------------------------------------


async def test_empty_report_is_zeroes_not_fabricated(client: AsyncClient) -> None:
    headers = await dev_login(client)
    response = await client.get(f"{API}/reports/summary", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["created"] == {
        "materials": 0,
        "lesson_plans": 0,
        "assignments": 0,
        "assessments": 0,
    }
    assert body["safe"] == {"materials": 0, "assessments": 0}
    assert body["assignments"] == {"active": 0, "overdue": 0, "due_soon": 0}
    assert body["materials_by_subject"] == []
    assert body["upcoming"] == []


async def test_counts_reflect_real_created_entities(client: AsyncClient) -> None:
    headers = await dev_login(client)
    await _create_plan(client, headers, title="План 1")
    await _create_plan(client, headers, title="План 2")
    await _create_assignment(client, headers, title="Задание 1")
    await client.post(
        f"{API}/materials",
        json={"title": "Материал", "subject": "История", "content": "", "is_protected": False},
        headers=headers,
    )

    response = await client.get(f"{API}/reports/summary", headers=headers)
    body = response.json()
    assert body["created"]["lesson_plans"] == 2
    assert body["created"]["assignments"] == 1
    assert body["created"]["materials"] == 1
    assert body["created"]["assessments"] == 0


async def test_assignment_states_computed_from_deadlines(client: AsyncClient) -> None:
    headers = await dev_login(client)
    now = dt.datetime.now(dt.UTC)
    await _create_assignment(
        client, headers, title="Просрочено", due_at=(now - dt.timedelta(days=2)).isoformat()
    )
    await _create_assignment(
        client, headers, title="Скоро", due_at=(now + dt.timedelta(days=2)).isoformat()
    )
    await _create_assignment(
        client, headers, title="Далеко", due_at=(now + dt.timedelta(days=20)).isoformat()
    )
    await _create_assignment(client, headers, title="Без срока", due_at=None)
    await _create_assignment(
        client, headers, title="Готово", due_at=(now - dt.timedelta(days=1)).isoformat(),
        status="done",
    )

    response = await client.get(f"{API}/reports/summary", headers=headers)
    body = response.json()
    assert body["assignments"] == {"active": 4, "overdue": 1, "due_soon": 1}


async def test_materials_by_subject_top_counts(client: AsyncClient) -> None:
    headers = await dev_login(client)
    for i in range(3):
        await client.post(
            f"{API}/materials",
            json={"title": f"М{i}", "subject": "История", "content": "", "is_protected": False},
            headers=headers,
        )
    await client.post(
        f"{API}/materials",
        json={"title": "М3", "subject": "Математика", "content": "", "is_protected": False},
        headers=headers,
    )
    # Blank subjects never appear in the distribution.
    await client.post(
        f"{API}/materials",
        json={"title": "М4", "subject": "", "content": "", "is_protected": False},
        headers=headers,
    )

    response = await client.get(f"{API}/reports/summary", headers=headers)
    subjects = {item["subject"]: item["count"] for item in response.json()["materials_by_subject"]}
    assert subjects == {"История": 3, "Математика": 1}


async def test_upcoming_merges_plans_and_deadlines(client: AsyncClient) -> None:
    headers = await dev_login(client)
    now = dt.datetime.now(dt.UTC)
    plan_date = (now + dt.timedelta(days=3)).date().isoformat()
    deadline = (now + dt.timedelta(days=1)).isoformat()

    await _create_plan(client, headers, title="Ближний урок", lesson_date=plan_date)
    await _create_assignment(client, headers, title="Скоро срок", due_at=deadline)

    response = await client.get(f"{API}/reports/summary", headers=headers)
    upcoming = response.json()["upcoming"]
    assert [item["type"] for item in upcoming] == ["assignment", "lesson_plan"]
    assert upcoming[0]["title"] == "Скоро срок"
    assert upcoming[1]["title"] == "Ближний урок"


async def test_safe_counts_are_current_state(client: AsyncClient) -> None:
    headers = await dev_login(client)
    await client.post(
        f"{API}/materials",
        json={"title": "Секрет", "subject": "", "content": "", "is_protected": True},
        headers=headers,
    )

    response = await client.get(f"{API}/reports/summary", headers=headers)
    assert response.json()["safe"] == {"materials": 1, "assessments": 0}


# --- ownership -----------------------------------------------------------------


async def test_report_never_mixes_teachers(client: AsyncClient) -> None:
    owner, stranger = await dev_login(client, "Анна"), await dev_login(client, "Борис")
    now = dt.datetime.now(dt.UTC)
    await _create_plan(
        client, owner, title="Чужой план",
        lesson_date=(now + dt.timedelta(days=1)).date().isoformat(),
    )
    await _create_assignment(
        client, owner, title="Чужой срок", due_at=(now + dt.timedelta(days=1)).isoformat()
    )

    response = await client.get(f"{API}/reports/summary", headers=stranger)
    body = response.json()
    assert body["created"]["lesson_plans"] == 0
    assert body["created"]["assignments"] == 0
    assert body["upcoming"] == []


# --- period handling ------------------------------------------------------------


async def test_period_shortcuts_accepted(client: AsyncClient) -> None:
    headers = await dev_login(client)
    for period in ("7d", "30d", "month"):
        response = await client.get(
            f"{API}/reports/summary?period={period}", headers=headers
        )
        assert response.status_code == 200, period


async def test_unknown_period_rejected(client: AsyncClient) -> None:
    headers = await dev_login(client)
    response = await client.get(f"{API}/reports/summary?period=year", headers=headers)
    assert response.status_code == 422


async def test_custom_period_requires_both_dates(client: AsyncClient) -> None:
    headers = await dev_login(client)

    missing = await client.get(f"{API}/reports/summary?period=custom", headers=headers)
    assert missing.status_code == 422

    inverted = await client.get(
        f"{API}/reports/summary?period=custom&date_from=2026-11-10&date_to=2026-11-01",
        headers=headers,
    )
    assert inverted.status_code == 422


async def test_custom_period_accepted(client: AsyncClient) -> None:
    headers = await dev_login(client)
    response = await client.get(
        f"{API}/reports/summary?period=custom&date_from=2026-11-01&date_to=2026-11-30",
        headers=headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["period"]["start"].startswith("2026-11-01")
    assert body["period"]["end"].startswith("2026-11-30")

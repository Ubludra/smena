"""Calendar API: one month, three sources, owner-scoped, honest dates.

The calendar is a pure read model: events appear exactly on the day their
source field (lesson_date / due_at / scheduled_at) points at, and never
outside the requested month.
"""

from __future__ import annotations

import datetime as dt
from typing import TYPE_CHECKING

from helpers import dev_login

if TYPE_CHECKING:
    from httpx import AsyncClient

API = "/api/v1"

# A month far from "today" so default-current-month tests stay independent.
YEAR, MONTH = 2030, 3  # March 2030, 31 days


async def _plan(
    client: AsyncClient, headers: dict[str, str], **overrides
) -> dict:
    payload = {
        "title": overrides.pop("title", "Урок"),
        "lesson_date": overrides.pop("lesson_date", None),
        **overrides,
    }
    response = await client.post(f"{API}/lesson-plans", json=payload, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


async def _assignment(
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


async def _assessment(
    client: AsyncClient, headers: dict[str, str], **overrides
) -> dict:
    payload = {
        "title": overrides.pop("title", "Проверочная"),
        "scheduled_at": overrides.pop("scheduled_at", None),
        **overrides,
    }
    response = await client.post(f"{API}/assessments", json=payload, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


async def _get(client: AsyncClient, headers: dict[str, str], **params) -> dict:
    response = await client.get(
        f"{API}/calendar",
        headers=headers,
        params={"year": YEAR, "month": MONTH, **params},
    )
    assert response.status_code == 200, response.text
    return response.json()


# --- authentication -----------------------------------------------------------


async def test_calendar_requires_auth(client: AsyncClient) -> None:
    response = await client.get(f"{API}/calendar")
    assert response.status_code == 401


# --- validation ----------------------------------------------------------------


async def test_invalid_month_is_422(client: AsyncClient) -> None:
    headers = await dev_login(client)
    for params in ({"year": YEAR, "month": 13}, {"year": YEAR, "month": 0},
                   {"year": 1999, "month": 1}, {"year": 2101, "month": 2}):
        response = await client.get(f"{API}/calendar", headers=headers, params=params)
        assert response.status_code == 422, params


async def test_defaults_to_current_month(client: AsyncClient) -> None:
    headers = await dev_login(client)
    response = await client.get(f"{API}/calendar", headers=headers)
    assert response.status_code == 200
    body = response.json()
    today = dt.datetime.now(tz=dt.UTC).date()
    assert (body["year"], body["month"]) == (today.year, today.month)
    assert body["events"] == []


# --- events ---------------------------------------------------------------------


async def test_month_is_empty_without_dated_entities(client: AsyncClient) -> None:
    headers = await dev_login(client)
    # Undated rows exist but never appear on any grid.
    await _plan(client, headers, title="Без даты", lesson_date=None)
    await _assignment(client, headers, title="Без срока", due_at=None)
    body = await _get(client, headers)
    assert body["events"] == []


async def test_all_three_event_types_land_on_their_days(client: AsyncClient) -> None:
    headers = await dev_login(client)
    await _plan(client, headers, title="Урок алгебры",
                lesson_date=f"{YEAR}-{MONTH:02d}-05", start_time="09:00")
    await _assignment(client, headers, title="Сочинение",
                      due_at=f"{YEAR}-{MONTH:02d}-12T23:59:00Z")
    await _assessment(client, headers, title="Контрольная",
                      scheduled_at=f"{YEAR}-{MONTH:02d}-20T10:30:00Z")

    body = await _get(client, headers)
    assert (body["year"], body["month"]) == (YEAR, MONTH)
    events = body["events"]
    assert [e["date"] for e in events] == [
        f"{YEAR}-{MONTH:02d}-05",
        f"{YEAR}-{MONTH:02d}-12",
        f"{YEAR}-{MONTH:02d}-20",
    ]
    assert [e["type"] for e in events] == ["lesson_plan", "assignment", "assessment"]
    assert events[0]["time"] == "09:00"
    assert events[1]["time"] == "23:59"
    assert events[1]["status"] == "active"


async def test_events_outside_month_do_not_leak(client: AsyncClient) -> None:
    headers = await dev_login(client)
    await _plan(client, headers, title="Февраль", lesson_date=f"{YEAR}-02-28")
    await _plan(client, headers, title="Апрель", lesson_date=f"{YEAR}-04-01")
    await _assignment(client, headers, title="Февральский срок",
                      due_at=f"{YEAR}-02-10T12:00:00Z")
    body = await _get(client, headers)
    assert body["events"] == []


async def test_done_and_archived_assignments_are_not_plans(client: AsyncClient) -> None:
    headers = await dev_login(client)
    await _assignment(client, headers, title="Сделано",
                      due_at=f"{YEAR}-{MONTH:02d}-08T12:00:00Z", status="done")
    await _assignment(client, headers, title="В архиве",
                      due_at=f"{YEAR}-{MONTH:02d}-09T12:00:00Z", status="archived")
    await _assignment(client, headers, title="Активно",
                      due_at=f"{YEAR}-{MONTH:02d}-10T12:00:00Z")
    body = await _get(client, headers)
    assert [e["title"] for e in body["events"]] == ["Активно"]


async def test_leap_february_window_is_correct(client: AsyncClient) -> None:
    headers = await dev_login(client)
    await _plan(client, headers, title="29 февраля", lesson_date="2032-02-29")
    body = await client.get(
        f"{API}/calendar", headers=headers, params={"year": 2032, "month": 2},
    )
    assert body.status_code == 200
    assert [e["title"] for e in body.json()["events"]] == ["29 февраля"]


# --- ownership -------------------------------------------------------------------


async def test_foreign_events_are_invisible(client: AsyncClient) -> None:
    owner, stranger = await dev_login(client, "Анна"), await dev_login(client, "Борис")
    await _plan(client, owner, title="Чужой урок",
                lesson_date=f"{YEAR}-{MONTH:02d}-07")
    body = await _get(client, stranger)
    assert body["events"] == []
    # The owner still sees the event.
    mine = await _get(client, owner)
    assert [e["title"] for e in mine["events"]] == ["Чужой урок"]

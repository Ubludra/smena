"""Report documents API: CRUD, validation, ownership, reports/summary intact.

Guards the route-ordering pitfall: /reports/{id} must not swallow the
pre-existing /reports/summary literal route.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from helpers import dev_login

if TYPE_CHECKING:
    from httpx import AsyncClient

API = "/api/v1"


async def _create(client: AsyncClient, headers: dict[str, str]) -> dict:
    response = await client.post(
        f"{API}/reports",
        json={
            "title": "Самообразование, 4 четверть",
            "subject": "Русский язык",
            "content": "## План\n- курс «Интерактив»",
        },
        headers=headers,
    )
    assert response.status_code == 201, response.text
    return response.json()


async def test_report_crud_roundtrip(client: AsyncClient) -> None:
    headers = await dev_login(client)
    created = await _create(client, headers)
    assert created["title"] == "Самообразование, 4 четверть"
    assert created["updated_at"]

    listed = await client.get(f"{API}/reports", headers=headers)
    assert listed.status_code == 200
    assert listed.json()["total"] == 1

    fetched = await client.get(f"{API}/reports/{created['id']}", headers=headers)
    assert fetched.json()["content"] == created["content"]

    patched = await client.patch(
        f"{API}/reports/{created['id']}", json={"content": "готово"}, headers=headers
    )
    assert patched.json()["content"] == "готово"
    assert patched.json()["title"] == created["title"]  # untouched

    assert (
        await client.delete(f"{API}/reports/{created['id']}", headers=headers)
    ).status_code == 204
    assert (
        await client.get(f"{API}/reports/{created['id']}", headers=headers)
    ).status_code == 404


async def test_blank_title_rejected(client: AsyncClient) -> None:
    headers = await dev_login(client)
    response = await client.post(f"{API}/reports", json={"title": "   "}, headers=headers)
    assert response.status_code == 422


async def test_reports_summary_route_still_works(client: AsyncClient) -> None:
    """/reports/summary must not be parsed as a report id (422 trap)."""
    headers = await dev_login(client)
    await _create(client, headers)
    response = await client.get(f"{API}/reports/summary?period=30d", headers=headers)
    assert response.status_code == 200
    assert "created" in response.json()


async def test_search_filters_by_title(client: AsyncClient) -> None:
    headers = await dev_login(client)
    await _create(client, headers)
    await client.post(f"{API}/reports", json={"title": "Классное руководство"}, headers=headers)
    found = await client.get(f"{API}/reports?search=классн", headers=headers)
    assert [r["title"] for r in found.json()["items"]] == ["Классное руководство"]


async def test_foreign_report_invisible(client: AsyncClient) -> None:
    anna = await dev_login(client, "Анна")
    boris = await dev_login(client, "Борис")
    created = await _create(client, anna)

    for response in (
        await client.get(f"{API}/reports/{created['id']}", headers=boris),
        await client.patch(
            f"{API}/reports/{created['id']}", json={"title": "хак"}, headers=boris
        ),
        await client.delete(f"{API}/reports/{created['id']}", headers=boris),
    ):
        assert response.status_code == 404

    listing = await client.get(f"{API}/reports", headers=boris)
    assert listing.json()["total"] == 0


async def test_requires_auth(client: AsyncClient) -> None:
    assert (await client.get(f"{API}/reports")).status_code == 401
    ghost = await client.get(f"{API}/reports/{uuid.uuid4()}", headers=await dev_login(client))
    assert ghost.status_code == 404


async def test_class_and_period_roundtrip(client: AsyncClient) -> None:
    """Report requisites (класс, период) persist through create and patch."""
    headers = await dev_login(client)
    created = await client.post(
        f"{API}/reports",
        json={
            "title": "Отчёт классного руководителя",
            "class_name": "4 «Б»",
            "period": "I четверть 2026/27",
        },
        headers=headers,
    )
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["class_name"] == "4 «Б»"
    assert body["period"] == "I четверть 2026/27"

    patched = await client.patch(
        f"{API}/reports/{body['id']}", json={"period": "II четверть"}, headers=headers
    )
    assert patched.json()["period"] == "II четверть"
    # Untouched requisite survives a partial update.
    assert patched.json()["class_name"] == "4 «Б»"


async def test_class_and_period_default_to_empty(client: AsyncClient) -> None:
    headers = await dev_login(client)
    created = await _create(client, headers)
    assert created["class_name"] == ""
    assert created["period"] == ""

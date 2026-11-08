"""Materials API: CRUD, filtering, validation, ownership (IDOR) enforcement.

The ownership tests here are the product's core security guarantee: knowing
another teacher's material id grants nothing — the API answers 404, the same
as for a missing object (no existence oracle).
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from helpers import dev_login, unlock_safe

if TYPE_CHECKING:
    from httpx import AsyncClient
    from sqlalchemy.ext.asyncio import AsyncSession

API = "/api/v1"


async def _login_pair(client: AsyncClient) -> tuple[dict[str, str], dict[str, str]]:
    return await dev_login(client, "Анна"), await dev_login(client, "Борис")


# --- authentication -----------------------------------------------------------


async def test_list_requires_auth(client: AsyncClient) -> None:
    response = await client.get(f"{API}/materials")
    assert response.status_code == 401


async def test_empty_list_for_new_teacher(client: AsyncClient) -> None:
    headers = await dev_login(client)
    response = await client.get(f"{API}/materials", headers=headers)
    assert response.status_code == 200
    assert response.json() == {"items": [], "total": 0}


# --- CRUD happy path ----------------------------------------------------------


async def test_create_read_update_delete(client: AsyncClient) -> None:
    headers = await dev_login(client)

    created = await client.post(
        f"{API}/materials",
        json={"title": "Карточки: падежи", "subject": "Русский язык", "content": "Р/И/Д..."},
        headers=headers,
    )
    assert created.status_code == 201
    material = created.json()
    assert material["title"] == "Карточки: падежи"
    assert material["is_protected"] is False
    material_id = material["id"]

    fetched = await client.get(f"{API}/materials/{material_id}", headers=headers)
    assert fetched.status_code == 200
    assert fetched.json()["content"] == "Р/И/Д..."

    patched = await client.patch(
        f"{API}/materials/{material_id}",
        json={"title": "Карточки: все падежи", "is_protected": True},
        headers=headers,
    )
    assert patched.status_code == 200
    assert patched.json()["title"] == "Карточки: все падежи"
    assert patched.json()["is_protected"] is True

    deleted = await client.delete(f"{API}/materials/{material_id}", headers=headers)
    assert deleted.status_code == 204

    after = await client.get(f"{API}/materials/{material_id}", headers=headers)
    assert after.status_code == 404


# --- filtering -----------------------------------------------------------------


async def test_search_and_protected_filter(client: AsyncClient) -> None:
    headers = await dev_login(client)
    await client.post(
        f"{API}/materials",
        json={"title": "Диктант осень", "subject": "Русский язык"},
        headers=headers,
    )
    await client.post(
        f"{API}/materials",
        json={"title": "Таблица умножения", "subject": "Математика", "is_protected": True},
        headers=headers,
    )

    by_text = await client.get(f"{API}/materials?search=диктант", headers=headers)
    assert [m["title"] for m in by_text.json()["items"]] == ["Диктант осень"]

    safe = await unlock_safe(client, headers)
    protected = await client.get(f"{API}/materials?only_protected=true", headers=safe)
    body = protected.json()
    assert body["total"] == 1
    assert body["items"][0]["title"] == "Таблица умножения"


async def test_list_order_is_newest_modified_first(client: AsyncClient) -> None:
    headers = await dev_login(client)
    first = (
        await client.post(f"{API}/materials", json={"title": "Первый"}, headers=headers)
    ).json()
    await client.post(f"{API}/materials", json={"title": "Второй"}, headers=headers)
    # Touch the first one: it becomes the most recently modified.
    await client.patch(f"{API}/materials/{first['id']}", json={"subject": "х"}, headers=headers)
    listing = await client.get(f"{API}/materials", headers=headers)
    assert [m["title"] for m in listing.json()["items"]] == ["Первый", "Второй"]


async def test_pagination(client: AsyncClient) -> None:
    headers = await dev_login(client)
    for i in range(5):
        await client.post(f"{API}/materials", json={"title": f"М{i}"}, headers=headers)
    page = await client.get(f"{API}/materials?limit=2&offset=2", headers=headers)
    body = page.json()
    assert body["total"] == 5
    assert len(body["items"]) == 2


# --- validation ----------------------------------------------------------------


async def test_title_validation(client: AsyncClient) -> None:
    headers = await dev_login(client)
    for bad in ("", "   ", "x" * 201):
        response = await client.post(f"{API}/materials", json={"title": bad}, headers=headers)
        assert response.status_code == 422, bad[:20]


async def test_unknown_field_rejected(client: AsyncClient) -> None:
    headers = await dev_login(client)
    response = await client.post(
        f"{API}/materials",
        json={"title": "ок", "owner_id": str(uuid.uuid4())},
        headers=headers,
    )
    assert response.status_code == 422


async def test_malformed_id_returns_422(client: AsyncClient) -> None:
    headers = await dev_login(client)
    response = await client.get(f"{API}/materials/not-a-uuid", headers=headers)
    assert response.status_code == 422


async def test_missing_material_returns_404(client: AsyncClient) -> None:
    headers = await dev_login(client)
    response = await client.get(f"{API}/materials/{uuid.uuid4()}", headers=headers)
    assert response.status_code == 404


# --- ownership / IDOR -----------------------------------------------------------


async def test_foreign_material_invisible_by_id(client: AsyncClient) -> None:
    anna, boris = await _login_pair(client)
    created = await client.post(
        f"{API}/materials",
        json={"title": "Личный журнал", "is_protected": True},
        headers=anna,
    )
    material_id = created.json()["id"]

    # Борис знает id — и не получает ничего. 404 (не 403): существование
    # чужого объекта не подтверждается.
    for response in (
        await client.get(f"{API}/materials/{material_id}", headers=boris),
        await client.patch(f"{API}/materials/{material_id}", json={"title": "хак"}, headers=boris),
        await client.delete(f"{API}/materials/{material_id}", headers=boris),
    ):
        assert response.status_code == 404

    listing = await client.get(f"{API}/materials", headers=boris)
    assert listing.json()["total"] == 0

    # Анне всё доступно — после разблокировки Сейфа (защищённый материал
    # без safe-токена не открывается даже владельцу).
    ok_locked = await client.get(f"{API}/materials/{material_id}", headers=anna)
    assert ok_locked.status_code == 403
    anna_safe = await unlock_safe(client, anna)
    ok = await client.get(f"{API}/materials/{material_id}", headers=anna_safe)
    assert ok.status_code == 200


async def test_anonymous_forgery_attempts(client: AsyncClient) -> None:
    anna, _ = await _login_pair(client)
    created = await client.post(f"{API}/materials", json={"title": "Т"}, headers=anna)
    material_id = created.json()["id"]
    anonymous = await client.get(f"{API}/materials/{material_id}")
    assert anonymous.status_code == 401


# --- database constraints (defense in depth beyond Pydantic) ---------------------


async def test_database_rejects_blank_title(db_session: AsyncSession) -> None:
    # Deliberately bypass API/validation: the CHECK constraint is the last line.
    from smena_api.db.models import Material, User

    user = User(max_user_id="constraint-user", display_name="Тест")
    db_session.add(user)
    await db_session.flush()
    db_session.add(Material(owner_id=user.id, title="   ", subject="", content=""))
    # The INSERT (and therefore the CHECK violation) happens at flush time.
    with pytest.raises(IntegrityError):
        await db_session.flush()


async def test_deleting_teacher_removes_materials(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    headers = await dev_login(client, "Временный")
    await client.post(f"{API}/materials", json={"title": "М"}, headers=headers)
    user_id = (await client.get(f"{API}/auth/me", headers=headers)).json()["id"]
    await db_session.execute(text("DELETE FROM users WHERE id = :id"), {"id": user_id})
    await db_session.commit()
    listing = await client.get(f"{API}/materials", headers=headers)
    assert listing.status_code == 401  # vanished user's token no longer works

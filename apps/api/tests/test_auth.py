"""Auth endpoints: dev login, /me, dev-auth disabling, bearer enforcement."""

from __future__ import annotations

from typing import TYPE_CHECKING

from helpers import dev_login, make_client

if TYPE_CHECKING:
    from collections.abc import Callable

    from fastapi import FastAPI
    from httpx import AsyncClient


API = "/api/v1"


async def test_dev_login_creates_teacher_and_returns_token(client: AsyncClient) -> None:
    response = await client.post(f"{API}/auth/dev-login", json={"display_name": "Ирина Петровна"})
    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["user"]["display_name"] == "Ирина Петровна"
    assert body["access_token"]


async def test_dev_login_is_idempotent_per_name(client: AsyncClient) -> None:
    first = await client.post(f"{API}/auth/dev-login", json={"display_name": "Пётр"})
    second = await client.post(f"{API}/auth/dev-login", json={"display_name": "Пётр"})
    assert first.json()["user"]["id"] == second.json()["user"]["id"]


async def test_me_returns_current_user(client: AsyncClient) -> None:
    headers = await dev_login(client, "Светлана")
    response = await client.get(f"{API}/auth/me", headers=headers)
    assert response.status_code == 200
    assert response.json()["display_name"] == "Светлана"


async def test_me_requires_token(client: AsyncClient) -> None:
    response = await client.get(f"{API}/auth/me")
    assert response.status_code == 401
    assert response.headers.get("WWW-Authenticate") == "Bearer"


async def test_me_rejects_garbage_token(client: AsyncClient) -> None:
    response = await client.get(f"{API}/auth/me", headers={"Authorization": "Bearer not.a.jwt"})
    assert response.status_code == 401


async def test_login_rejects_blank_name(client: AsyncClient) -> None:
    response = await client.post(f"{API}/auth/dev-login", json={"display_name": "   "})
    assert response.status_code == 422


async def test_login_rejects_unknown_fields(client: AsyncClient) -> None:
    # The client cannot inject identity fields (e.g. user_id): unknown keys 422.
    response = await client.post(f"{API}/auth/dev-login", json={"display_name": "А", "user_id": 1})
    assert response.status_code == 422


async def test_dev_login_hidden_when_disabled(app_factory: Callable[..., FastAPI]) -> None:
    """With ENABLE_DEV_AUTH=false the endpoint answers 404 — fail closed."""
    application = app_factory(enable_dev_auth=False)
    async with application.router.lifespan_context(application), make_client(application) as ac:
        response = await ac.post(f"{API}/auth/dev-login", json={"display_name": "Кто-то"})
        assert response.status_code == 404

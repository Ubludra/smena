"""Safe unlock: password binding, mismatch rejection, gating of protected data.

The unlock is knowledge-of-password (dedicated Safe password, scrypt-hashed
server-side — see api/routes/safe.py docstring). These tests pin the honest
contract: first unlock sets the password, wrong password 403s, protected
reads need the token.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from helpers import SAFE_PASSWORD, dev_login, unlock_safe

if TYPE_CHECKING:
    from fastapi import FastAPI
    from httpx import AsyncClient

API = "/api/v1"


async def test_status_starts_without_password(client: AsyncClient) -> None:
    headers = await dev_login(client)
    response = await client.get(f"{API}/safe/status", headers=headers)
    assert response.status_code == 200
    assert response.json() == {"has_password": False}


async def test_first_unlock_sets_password_and_returns_token(client: AsyncClient) -> None:
    headers = await dev_login(client)
    response = await client.post(
        f"{API}/safe/unlock", json={"password": SAFE_PASSWORD}, headers=headers
    )
    assert response.status_code == 200
    body = response.json()
    assert body["token"]
    assert body["expires_in_seconds"] > 0

    status = await client.get(f"{API}/safe/status", headers=headers)
    # Status confirms only THAT a password exists — no hints of any kind.
    assert status.json() == {"has_password": True}


async def test_wrong_password_is_rejected_after_setting(client: AsyncClient) -> None:
    headers = await unlock_safe(client, await dev_login(client))
    response = await client.post(
        f"{API}/safe/unlock", json={"password": "osinovye-sani"}, headers=headers
    )
    assert response.status_code == 403


async def test_second_near_miss_still_rejected(client: AsyncClient) -> None:
    headers = await dev_login(client)
    await unlock_safe(client, headers)
    # A prefix of the real password must not pass either.
    response = await client.post(
        f"{API}/safe/unlock",
        json={"password": SAFE_PASSWORD[:-2]},
        headers=headers,
    )
    assert response.status_code == 403


async def test_short_password_is_422(client: AsyncClient) -> None:
    headers = await dev_login(client)
    response = await client.post(
        f"{API}/safe/unlock", json={"password": "кот"}, headers=headers
    )
    assert response.status_code == 422


async def test_stored_password_is_not_plaintext(
    client: AsyncClient, app: FastAPI
) -> None:
    """The DB keeps a salted scrypt digest, never the raw password."""
    from sqlalchemy import select

    from smena_api.db.models import User

    await unlock_safe(client, await dev_login(client, "Хранитель"))
    session_factory = app.state.db.session_factory
    async with session_factory() as session:
        user = (
            await session.execute(select(User).where(User.display_name == "Хранитель"))
        ).scalar_one()
    stored = user.safe_password_hash or ""
    assert stored.startswith("scrypt$")
    assert SAFE_PASSWORD not in stored
    # Distinct accounts setting the same password get distinct salts.
    await unlock_safe(client, await dev_login(client, "Хранительница"))
    async with session_factory() as session:
        other = (
            await session.execute(
                select(User).where(User.display_name == "Хранительница")
            )
        ).scalar_one()
    assert other.safe_password_hash != stored


async def test_protected_listing_requires_token(client: AsyncClient) -> None:
    headers = await dev_login(client)
    await client.post(
        f"{API}/materials", json={"title": "Секрет", "is_protected": True}, headers=headers
    )

    locked = await client.get(f"{API}/materials?only_protected=true", headers=headers)
    assert locked.status_code == 403

    safe = await unlock_safe(client, headers)
    unlocked = await client.get(f"{API}/materials?only_protected=true", headers=safe)
    assert unlocked.status_code == 200
    assert unlocked.json()["total"] == 1

    # A garbage token is the same as none.
    forged = {**headers, "X-Safe-Token": "not-a-jwt"}
    assert (
        await client.get(f"{API}/materials?only_protected=true", headers=forged)
    ).status_code == 403


async def test_safe_token_is_not_an_access_token(client: AsyncClient) -> None:
    """The two token types are not interchangeable in either direction."""
    headers = await unlock_safe(client, await dev_login(client))
    safe_token = headers["X-Safe-Token"]
    access_token = headers["Authorization"].removeprefix("Bearer ")

    # Safe token as bearer -> rejected.
    fake = {"Authorization": f"Bearer {safe_token}"}
    assert (await client.get(f"{API}/materials", headers=fake)).status_code == 401
    # Access token as safe header -> 403 (auth OK, safe gate closed).
    forged = {"Authorization": f"Bearer {access_token}", "X-Safe-Token": access_token}
    assert (
        await client.get(f"{API}/materials?only_protected=true", headers=forged)
    ).status_code == 403


async def test_safe_token_is_bound_to_its_owner(client: AsyncClient) -> None:
    anna = await unlock_safe(client, await dev_login(client, "Анна"))
    boris = await dev_login(client, "Борис")
    anna_material = await client.post(
        f"{API}/materials",
        json={"title": "Аннин секрет", "is_protected": True},
        headers=anna,
    )
    material_id = anna_material.json()["id"]

    # Борис не проходит гейт чужим токеном (свой access + анин safe-токен).
    stolen = {
        "Authorization": boris["Authorization"],
        "X-Safe-Token": anna["X-Safe-Token"],
    }
    assert (
        await client.get(f"{API}/materials?only_protected=true", headers=stolen)
    ).status_code == 403
    assert (
        await client.get(f"{API}/materials/{material_id}", headers=stolen)
    ).status_code == 404


async def test_assessments_are_gated_too(client: AsyncClient) -> None:
    headers = await dev_login(client)
    created = await client.post(
        f"{API}/assessments",
        json={
            "title": "Секретная контрольная",
            "is_protected": True,
            "questions": [
                {
                    "text": "Сколько будет 2+2?",
                    "type": "single",
                    "options": ["4", "5"],
                    "correct": [0],
                }
            ],
        },
        headers=headers,
    )
    assessment_id = created.json()["id"]

    assert (
        await client.get(f"{API}/assessments?only_protected=true", headers=headers)
    ).status_code == 403
    assert (
        await client.get(f"{API}/assessments/{assessment_id}", headers=headers)
    ).status_code == 403

    safe = await unlock_safe(client, headers)
    assert (
        await client.get(f"{API}/assessments/{assessment_id}", headers=safe)
    ).status_code == 200

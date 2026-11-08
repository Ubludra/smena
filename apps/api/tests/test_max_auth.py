"""MAX launch-data verification — the real production login path.

Unit tests exercise the documented algorithm directly; route tests cover the
honest deployment states (no token → 503, forged → 401, valid → session).
"""

import time
from typing import TYPE_CHECKING

import pytest

from helpers import build_init_data, make_client
from smena_api.integrations.max_auth import (
    MaxInvalidData,
    MaxStaleData,
    compute_init_data_hash,
    identity_from_init_data,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from fastapi import FastAPI
    from httpx import AsyncClient


BOT_TOKEN = "test-bot-token-123"
USER = {"id": 4242, "first_name": "Мария", "last_name": "Смирнова", "username": "msmirnova"}

API = "/api/v1"


# --- unit: the documented algorithm -----------------------------------------


def test_signature_roundtrip_matches_documented_algorithm() -> None:
    init_data = build_init_data(BOT_TOKEN, user=USER)
    # compute_init_data_hash verifies internally; success = no raise.
    compute_init_data_hash(init_data, BOT_TOKEN)


def test_wrong_bot_token_fails_signature() -> None:
    init_data = build_init_data(BOT_TOKEN, user=USER)
    with pytest.raises(MaxInvalidData):
        compute_init_data_hash(init_data, "attacker-guessed-token")


def test_tampered_payload_fails_signature() -> None:
    init_data = build_init_data(BOT_TOKEN, user=USER)
    # Swap identity to another MAX user id after signing: must not verify.
    tampered = init_data.replace("%22id%22%3A4242", "%22id%22%3A9999")
    if tampered == init_data:  # the encoding detail differed; tamper via params
        tampered = init_data.replace("4242", "9999")
    with pytest.raises(MaxInvalidData):
        compute_init_data_hash(tampered, BOT_TOKEN)


def test_missing_hash_is_invalid() -> None:
    with pytest.raises(MaxInvalidData):
        compute_init_data_hash("query_id=x&auth_date=1", BOT_TOKEN)


def test_duplicate_parameter_is_invalid() -> None:
    init_data = build_init_data(BOT_TOKEN, user=USER)
    with pytest.raises(MaxInvalidData):
        compute_init_data_hash(init_data + "&query_id=duplicate", BOT_TOKEN)


def test_stale_auth_date_is_rejected() -> None:
    old = build_init_data(BOT_TOKEN, user=USER, auth_date=int(time.time()) - 7200)
    with pytest.raises(MaxStaleData):
        identity_from_init_data(old, BOT_TOKEN, max_age_seconds=3600)


def test_identity_extraction() -> None:
    init_data = build_init_data(BOT_TOKEN, user=USER)
    identity = identity_from_init_data(init_data, BOT_TOKEN, max_age_seconds=3600)
    assert identity.max_user_id == "4242"
    assert identity.display_name == "Мария Смирнова"


# --- route: honest deployment states ----------------------------------------


async def test_max_launch_without_token_reports_not_configured(client: "AsyncClient") -> None:
    init_data = build_init_data(BOT_TOKEN, user=USER)
    response = await client.post(f"{API}/auth/max-launch", json={"init_data": init_data})
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "MAX_NOT_CONFIGURED"


async def test_max_launch_valid_signature_creates_session(
    app_factory: "Callable[..., FastAPI]",
) -> None:
    application = app_factory(max_bot_token=BOT_TOKEN)
    async with application.router.lifespan_context(application), make_client(application) as ac:
        init_data = build_init_data(BOT_TOKEN, user=USER)
        response = await ac.post(f"{API}/auth/max-launch", json={"init_data": init_data})
        assert response.status_code == 200
        body = response.json()
        assert body["user"]["display_name"] == "Мария Смирнова"

        # Full vertical proof: the issued session can actually work.
        headers = {"Authorization": f"Bearer {body['access_token']}"}
        created = await ac.post(
            f"{API}/materials", json={"title": "Карточка дня"}, headers=headers
        )
        assert created.status_code == 201


async def test_max_launch_forged_signature_rejected(
    app_factory: "Callable[..., FastAPI]",
) -> None:
    application = app_factory(max_bot_token=BOT_TOKEN)
    async with application.router.lifespan_context(application), make_client(application) as ac:
        forged = build_init_data("someone-elses-token", user=USER)
        response = await ac.post(f"{API}/auth/max-launch", json={"init_data": forged})
        assert response.status_code == 401
        assert response.json()["detail"]["code"] == "MAX_INVALID_LAUNCH_DATA"


async def test_max_launch_same_platform_user_maps_to_same_account(
    app_factory: "Callable[..., FastAPI]",
) -> None:
    application = app_factory(max_bot_token=BOT_TOKEN)
    async with application.router.lifespan_context(application), make_client(application) as ac:
        first = await ac.post(
            f"{API}/auth/max-launch", json={"init_data": build_init_data(BOT_TOKEN, user=USER)}
        )
        second = await ac.post(
            f"{API}/auth/max-launch", json={"init_data": build_init_data(BOT_TOKEN, user=USER)}
        )
        assert first.json()["user"]["id"] == second.json()["user"]["id"]

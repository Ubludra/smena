"""E2E report chat: invite links, membership isolation, ciphertext relay.

The server never sees plaintext — tests pin the access rules around that:
wrong invite token and unknown room are indistinguishable (404), non-members
cannot read or post, and the invite secret appears exactly once.
"""

from __future__ import annotations

import re
import uuid
from typing import TYPE_CHECKING

from helpers import dev_login

if TYPE_CHECKING:
    from httpx import AsyncClient

API = "/api/v1"

# What a real client sends after WebCrypto AES-GCM (opaque base64 here).
CIPHER = "SGVsbG8gZW5jcnlwdGVkIHdvcmxkIGJhc2U2NA=="


async def _create_room(client: AsyncClient, headers: dict[str, str]) -> dict:
    response = await client.post(
        f"{API}/report-rooms", json={"name": "9А — административная"}, headers=headers
    )
    assert response.status_code == 201, response.text
    return response.json()


async def test_create_returns_invite_link_once(client: AsyncClient) -> None:
    headers = await dev_login(client)
    room = await _create_room(client, headers)
    # Secret lives in the hash-route fragment, 32 b64url chars.
    match = re.fullmatch(r"#/chat/([0-9a-f-]{36})/([A-Za-z0-9_-]{32})", room["invite_path"])
    assert match, room["invite_path"]
    assert match.group(1) == room["id"]

    # Never repeated: listing rooms carries no secret.
    rooms = await client.get(f"{API}/report-rooms", headers=headers)
    assert rooms.json()[0]["name"] == "9А — административная"
    assert "invite" not in rooms.json()[0]


async def test_join_with_valid_token_allows_traffic(client: AsyncClient) -> None:
    anna = await dev_login(client, "Анна")
    boris = await dev_login(client, "Борис")
    room = await _create_room(client, anna)
    room_id, token = room["invite_path"].removeprefix("#/chat/").split("/")

    joined = await client.post(
        f"{API}/report-rooms/join",
        json={"room_id": room_id, "invite_token": token},
        headers=boris,
    )
    assert joined.status_code == 200

    posted = await client.post(
        f"{API}/report-rooms/{room_id}/messages",
        json={"ciphertext": CIPHER},
        headers=boris,
    )
    assert posted.status_code == 201
    message = posted.json()
    assert message["ciphertext"] == CIPHER

    seen = await client.get(f"{API}/report-rooms/{room_id}/messages", headers=anna)
    assert [m["ciphertext"] for m in seen.json()] == [CIPHER]
    assert seen.json()[0]["sender_id"] == message["sender_id"]


async def test_wrong_token_and_unknown_room_are_identical_404(
    client: AsyncClient,
) -> None:
    anna = await dev_login(client, "Анна")
    boris = await dev_login(client, "Борис")
    room = await _create_room(client, anna)
    room_id = room["id"]

    bad_token = await client.post(
        f"{API}/report-rooms/join",
        json={"room_id": room_id, "invite_token": "x" * 32},
        headers=boris,
    )
    bad_room = await client.post(
        f"{API}/report-rooms/join",
        json={"room_id": str(uuid.uuid4()), "invite_token": "x" * 32},
        headers=boris,
    )
    assert bad_token.status_code == bad_room.status_code == 404
    assert bad_token.json() == bad_room.json()


async def test_non_member_cannot_read_or_post(client: AsyncClient) -> None:
    anna = await dev_login(client, "Анна")
    stranger = await dev_login(client, "Борис")
    room = await _create_room(client, anna)
    room_id = room["id"]

    assert (
        await client.get(f"{API}/report-rooms/{room_id}/messages", headers=stranger)
    ).status_code == 404
    assert (
        await client.post(
            f"{API}/report-rooms/{room_id}/messages",
            json={"ciphertext": CIPHER},
            headers=stranger,
        )
    ).status_code == 404
    # Stranger's room list doesn't contain it.
    rooms = await client.get(f"{API}/report-rooms", headers=stranger)
    assert rooms.json() == []


async def test_join_is_idempotent(client: AsyncClient) -> None:
    anna = await dev_login(client, "Анна")
    boris = await dev_login(client, "Борис")
    room = await _create_room(client, anna)
    room_id, token = room["invite_path"].removeprefix("#/chat/").split("/")
    body = {"room_id": room_id, "invite_token": token}

    first = await client.post(f"{API}/report-rooms/join", json=body, headers=boris)
    second = await client.post(f"{API}/report-rooms/join", json=body, headers=boris)
    assert first.status_code == second.status_code == 200

    rooms = await client.get(f"{API}/report-rooms", headers=boris)
    assert len(rooms.json()) == 1


async def test_message_cursor_pagination(client: AsyncClient) -> None:
    anna = await dev_login(client, "Анна")
    room = await _create_room(client, anna)
    room_id = room["id"]
    first = await client.post(
        f"{API}/report-rooms/{room_id}/messages",
        json={"ciphertext": "AAAA"},
        headers=anna,
    )
    await client.post(
        f"{API}/report-rooms/{room_id}/messages",
        json={"ciphertext": "BBBB"},
        headers=anna,
    )
    after = await client.get(
        f"{API}/report-rooms/{room_id}/messages?after={first.json()['id']}",
        headers=anna,
    )
    assert [m["ciphertext"] for m in after.json()] == ["BBBB"]


async def test_oversized_ciphertext_rejected(client: AsyncClient) -> None:
    anna = await dev_login(client, "Анна")
    room = await _create_room(client, anna)
    response = await client.post(
        f"{API}/report-rooms/{room['id']}/messages",
        json={"ciphertext": "A" * 300_001},
        headers=anna,
    )
    assert response.status_code == 422


async def test_requires_auth(client: AsyncClient) -> None:
    assert (await client.get(f"{API}/report-rooms")).status_code == 401
    assert (
        await client.post(f"{API}/report-rooms", json={"name": "т"})
    ).status_code == 401

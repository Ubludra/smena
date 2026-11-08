"""Passkey change security boundaries and persistent password-attempt throttling."""

import json
from types import SimpleNamespace

from httpx import ASGITransport, AsyncClient

from helpers import SAFE_PASSWORD, dev_login, unlock_safe
from smena_api.api.routes import safe_security

API = "/api/v1"


async def test_change_cannot_start_without_enrolled_key(client: AsyncClient) -> None:
    headers = await dev_login(client)
    await unlock_safe(client, headers)
    response = await client.post(f"{API}/safe/security/change/request", headers=headers)
    assert response.status_code == 503  # No configured WebAuthn RP: fail closed.


async def test_wrong_password_enrollment_is_throttled(app_factory, monkeypatch) -> None:
    application = app_factory(
        passkey_rp_id="localhost", passkey_origin="http://localhost"
    )
    async with application.router.lifespan_context(application), AsyncClient(
        transport=ASGITransport(app=application), base_url="http://testserver"
    ) as client:
        headers = await dev_login(client, "Ольга")
        await unlock_safe(client, headers)
        for _ in range(5):
            response = await client.post(
                f"{API}/safe/security/enroll/options",
                json={"current_password": "wrong-password"},
                headers=headers,
            )
            assert response.status_code == 403
        blocked = await client.post(
            f"{API}/safe/unlock",
            json={"password": SAFE_PASSWORD},
            headers=headers,
        )
        assert blocked.status_code == 429


async def test_change_requires_passkey_and_revokes_old_safe_token(
    app_factory, monkeypatch
) -> None:
    application = app_factory(
        passkey_rp_id="localhost", passkey_origin="http://localhost"
    )
    challenge = b"test-challenge-32-byte-seed-12345"
    monkeypatch.setattr(
        safe_security, "generate_registration_options",
        lambda **kwargs: SimpleNamespace(challenge=challenge),
    )
    monkeypatch.setattr(
        safe_security, "generate_authentication_options",
        lambda **kwargs: SimpleNamespace(challenge=challenge),
    )
    monkeypatch.setattr(
        safe_security, "options_to_json",
        lambda options: json.dumps({"challenge": "mock-challenge"}),
    )
    monkeypatch.setattr(
        safe_security, "verify_registration_response",
        lambda **kwargs: SimpleNamespace(
            credential_id=b"test-credential-id",
            credential_public_key=b"test-public-key",
            sign_count=0,
        ),
    )
    monkeypatch.setattr(
        safe_security, "verify_authentication_response",
        lambda **kwargs: SimpleNamespace(
            credential_id=b"test-credential-id", new_sign_count=1
        ),
    )
    async with application.router.lifespan_context(application), AsyncClient(
        transport=ASGITransport(app=application), base_url="http://testserver"
    ) as client:
        headers = await dev_login(client, "Ирина")
        unlocked = await unlock_safe(client, headers)
        initial = await client.get(
            f"{API}/safe/security/status", headers=headers
        )
        assert initial.json()["registered"] is False

        start = await client.post(
            f"{API}/safe/security/enroll/options",
            json={"current_password": SAFE_PASSWORD},
            headers=headers,
        )
        assert start.status_code == 200
        registered = await client.post(
            f"{API}/safe/security/enroll/finish",
            json={"credential": {"id": "test"}},
            headers=headers,
        )
        assert registered.status_code == 200

        requested = await client.post(
            f"{API}/safe/security/change/request", headers=headers
        )
        assert requested.status_code == 200
        assert requested.json() == {"pending": True}
        options = await client.post(
            f"{API}/safe/security/change/options", headers=headers
        )
        assert options.status_code == 200

        changed = await client.post(
            f"{API}/safe/security/change/finish",
            json={
                "credential": {"id": "test"},
                "new_password": "new-strong-password-2026",
            },
            headers=headers,
        )
        assert changed.status_code == 200
        assert changed.json() == {"changed": True}

        replay = await client.post(
            f"{API}/safe/security/change/finish",
            json={
                "credential": {"id": "test"},
                "new_password": "attacker-password",
            },
            headers=headers,
        )
        assert replay.status_code == 409

        old = await client.get(
            f"{API}/materials?only_protected=true", headers=unlocked
        )
        assert old.status_code == 403
        old_password = await client.post(
            f"{API}/safe/unlock",
            json={"password": SAFE_PASSWORD},
            headers=headers,
        )
        assert old_password.status_code == 403
        new_password = await client.post(
            f"{API}/safe/unlock",
            json={"password": "new-strong-password-2026"},
            headers=headers,
        )
        assert new_password.status_code == 200

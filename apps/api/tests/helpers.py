"""Small helpers shared by API tests."""

from __future__ import annotations

import hashlib
import hmac
import json
import time
import urllib.parse
from typing import TYPE_CHECKING

from httpx import ASGITransport, AsyncClient

if TYPE_CHECKING:
    from fastapi import FastAPI


def make_client(application: FastAPI) -> AsyncClient:
    """Client bound to an explicitly-created app (for custom-settings tests)."""
    return AsyncClient(transport=ASGITransport(app=application), base_url="http://testserver")


API = "/api/v1"


async def dev_login(client: AsyncClient, display_name: str = "Мария") -> dict[str, str]:
    """Log in via the dev flow and return auth headers for that teacher."""
    response = await client.post(f"{API}/auth/dev-login", json={"display_name": display_name})
    assert response.status_code == 200, response.text
    token: str = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


SAFE_PASSWORD = "seif-parol-2026"  # fixture password for the Safe unlock tests


async def unlock_safe(
    client: AsyncClient, headers: dict[str, str], password: str = SAFE_PASSWORD
) -> dict[str, str]:
    """Unlock the Safe and return auth headers carrying the X-Safe-Token."""
    response = await client.post(
        f"{API}/safe/unlock", json={"password": password}, headers=headers
    )
    assert response.status_code == 200, response.text
    safe_token: str = response.json()["token"]
    return {**headers, "X-Safe-Token": safe_token}


def build_init_data(bot_token: str, *, user: dict, auth_date: int | None = None) -> str:
    """Assemble a *correctly signed* WebApp.initData (fixtures may tamper later).

    Mirrors the official algorithm (dev.max.ru/docs/webapps/validation) so the
    verifier is tested against an independent reimplementation of the spec.
    """
    params = {
        "query_id": "AAH-hasdf-test",
        "user": json.dumps(user, ensure_ascii=False, separators=(",", ":")),
        "auth_date": str(auth_date if auth_date is not None else int(time.time())),
    }
    launch_params = "\n".join(f"{k}={params[k]}" for k in sorted(params))
    secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    signature = hmac.new(secret_key, launch_params.encode(), hashlib.sha256).hexdigest()
    params["hash"] = signature
    return "&".join(f"{k}={urllib.parse.quote(v, safe='')}" for k, v in params.items())

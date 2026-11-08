"""MAX mini-app launch-data verification — REAL implementation.

Implements the algorithm documented at
https://dev.max.ru/docs/webapps/validation (accessed 2026-10-22):

1. parse the ``initData`` URL-encoded ``key=value`` string (from
   ``WebApp.initData`` / the ``#WebAppData=`` fragment);
2. require the ``hash`` parameter exactly once, exclude it from signing;
3. URL-decode values, sort pairs by key, join as ``key1=value1\\nkey2=value2``;
4. ``secret_key = HMAC-SHA256(key="WebAppData", msg=BOT_TOKEN)``;
5. ``computed = hex(HMAC-SHA256(key=secret_key, msg=launch_params))``;
6. constant-time compare with the received ``hash``.

Freshness: ``auth_date`` older than ``MAX_INIT_DATA_MAX_AGE_SECONDS``
(official recommendation: 1 hour) is rejected — a captured launch payload
must not unlock an account next week.

The bot token is the signing secret and comes from ``MAX_BOT_TOKEN``.
Without it verification is impossible by construction; the API then answers
503 MAX_NOT_CONFIGURED (explicit, honest state — never a bypass).

Nothing here is invented: every field and step maps to the cited page. Items
the official docs leave open (e.g. which extra parameters may appear) are
handled generically: unknown parameters participate in the signature exactly
as sent, which is what the documented algorithm prescribes.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time
import urllib.parse
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from smena_api.config import Settings

_HASH_PARAM = "hash"
_SECRET_KEY_MESSAGE = b"WebAppData"


class MaxAuthError(Exception):
    """Base class for launch-data verification failures."""


class MaxNotConfigured(MaxAuthError):
    """MAX_BOT_TOKEN is absent — verification cannot be performed."""


class MaxInvalidData(MaxAuthError):
    """Malformed payload or signature mismatch (forged/corrupted)."""


class MaxStaleData(MaxAuthError):
    """auth_date too old — replay window exceeded."""


@dataclass(frozen=True)
class MaxIdentity:
    """Trusted identity extracted from a verified launch context."""

    max_user_id: str
    display_name: str


def _sign(secret_key: bytes, launch_params: str) -> str:
    return hmac.new(secret_key, launch_params.encode("utf-8"), hashlib.sha256).hexdigest()


def _secret_key(bot_token: str) -> bytes:
    return hmac.new(_SECRET_KEY_MESSAGE, bot_token.encode("utf-8"), hashlib.sha256).digest()


def compute_init_data_hash(init_data: str, bot_token: str) -> str:
    """Recompute the signature over ``init_data`` exactly as the docs prescribe."""
    pairs = urllib.parse.parse_qsl(init_data, keep_blank_values=True)
    if not pairs:
        raise MaxInvalidData("empty init data")
    keys = [key for key, _ in pairs]
    # Documented step 1: every parameter must occur exactly once. Duplicate
    # keys would let an attacker smuggle a second value past naive parsing.
    if len(keys) != len(set(keys)):
        raise MaxInvalidData("duplicate parameters")
    if _HASH_PARAM not in keys:
        raise MaxInvalidData("hash parameter missing")

    received = dict(pairs)[_HASH_PARAM]
    launch_params = "\n".join(
        f"{key}={value}" for key, value in sorted(p for p in pairs if p[0] != _HASH_PARAM)
    )
    computed = _sign(_secret_key(bot_token), launch_params)
    if not hmac.compare_digest(computed, received):
        raise MaxInvalidData("signature mismatch")
    return received


def identity_from_init_data(init_data: str, bot_token: str, *, max_age_seconds: int) -> MaxIdentity:
    """Verify signature + freshness, then return the trusted identity."""
    compute_init_data_hash(init_data, bot_token)  # raises MaxInvalidData

    params = dict(urllib.parse.parse_qsl(init_data, keep_blank_values=True))
    try:
        auth_date = int(params["auth_date"])
    except (KeyError, ValueError) as exc:
        raise MaxInvalidData("auth_date missing or not numeric") from exc
    if time.time() - auth_date > max_age_seconds:
        raise MaxStaleData("init data too old")

    try:
        user = json.loads(params["user"])
    except KeyError as exc:
        raise MaxInvalidData("user missing") from exc
    except json.JSONDecodeError as exc:
        raise MaxInvalidData("user is not JSON") from exc
    if not isinstance(user, dict) or "id" not in user:
        raise MaxInvalidData("user.id missing")

    first = str(user.get("first_name", "")).strip()
    last = str(user.get("last_name", "")).strip()
    display_name = " ".join(part for part in (first, last) if part) or "Пользователь MAX"
    return MaxIdentity(max_user_id=str(user["id"]), display_name=display_name[:120])


def verify_launch_context(init_data: str, settings: Settings) -> MaxIdentity:
    """Entry point used by the API layer.

    Raises:
        MaxNotConfigured: no bot token configured.
        MaxInvalidData / MaxStaleData: rejected payload.
    """
    if settings.max_bot_token is None:
        raise MaxNotConfigured("MAX_BOT_TOKEN is not configured")
    token = settings.max_bot_token.get_secret_value()
    if not token:
        raise MaxNotConfigured("MAX_BOT_TOKEN is empty")
    return identity_from_init_data(
        init_data, token, max_age_seconds=settings.max_init_data_max_age_seconds
    )

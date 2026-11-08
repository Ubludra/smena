"""Access-token issuing and verification (JWT HS256, minimal surface).

Tokens are signed with ``SECRET_KEY`` and carry only what the API needs:
subject (user id), issued-at and expiry. Signature and expiry are verified
on every request; anything else is intentionally absent.

Server-side revocation is not implemented (documented limitation): the token
is short-lived and the product ships no logout-critical workflows yet. If
long-lived sessions become a requirement, store token ids in the database and
check them here — do not lengthen TTLs to compensate.
"""

from __future__ import annotations

import datetime as dt
import uuid
from dataclasses import dataclass

import jwt

_TOKEN_TYPE = "smena-access"  # noqa: S105  # token marker, not a credential
_SAFE_TOKEN_TYPE = "smena-safe"  # noqa: S105  # second-factor Safe unlock, not a credential


class TokenError(Exception):
    """Raised for any invalid/expired/foreign token."""


@dataclass(frozen=True)
class TokenClaims:
    user_id: uuid.UUID


def issue_access_token(*, secret: str, user_id: uuid.UUID, ttl_seconds: int) -> str:
    now = dt.datetime.now(dt.UTC)
    payload = {
        "sub": str(user_id),
        "typ": _TOKEN_TYPE,
        "iat": int(now.timestamp()),
        "exp": int((now + dt.timedelta(seconds=ttl_seconds)).timestamp()),
    }
    token: str = jwt.encode(payload, secret, algorithm="HS256")
    return token


def issue_safe_token(*, secret: str, user_id: uuid.UUID, ttl_seconds: int) -> str:
    """Short-lived Safe-unlock token (separate ``typ`` from access tokens).

    Stateless by design: the lock button forgets the token client-side; the
    server-side guarantee is the expiry (minutes) + the password re-check to
    mint a new one. Revocation lists would need storage; a 15-minute window
    after a leaked token is the documented, accepted bound.
    """
    now = dt.datetime.now(dt.UTC)
    payload = {
        "sub": str(user_id),
        "typ": _SAFE_TOKEN_TYPE,
        "iat": int(now.timestamp()),
        "exp": int((now + dt.timedelta(seconds=ttl_seconds)).timestamp()),
    }
    token: str = jwt.encode(payload, secret, algorithm="HS256")
    return token


def verify_safe_token(*, secret: str, token: str) -> TokenClaims:
    """Return claims or raise ``TokenError`` (mirror of access verification)."""
    try:
        payload = jwt.decode(token, secret, algorithms=["HS256"], subject=None)
    except jwt.PyJWTError as exc:
        raise TokenError("invalid token") from exc
    if payload.get("typ") != _SAFE_TOKEN_TYPE:
        raise TokenError("wrong token type")
    try:
        return TokenClaims(user_id=uuid.UUID(str(payload.get("sub", ""))))
    except (ValueError, TypeError) as exc:
        raise TokenError("invalid subject") from exc


def verify_access_token(*, secret: str, token: str) -> TokenClaims:
    """Return claims or raise ``TokenError``. Never partially trusts a token."""
    try:
        # Pin the algorithm: never let attacker-controlled headers pick it
        # (classic "alg: none"/algorithm-confusion class).
        payload = jwt.decode(token, secret, algorithms=["HS256"], subject=None)
    except jwt.PyJWTError as exc:  # signature, expiry, malformed, ...
        raise TokenError("invalid token") from exc

    if payload.get("typ") != _TOKEN_TYPE:
        raise TokenError("wrong token type")
    try:
        return TokenClaims(user_id=uuid.UUID(str(payload.get("sub", ""))))
    except (ValueError, TypeError) as exc:
        raise TokenError("invalid subject") from exc

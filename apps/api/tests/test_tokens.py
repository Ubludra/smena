"""Access-token lifecycle tests (core/tokens.py)."""

import time
import uuid

import jwt
import pytest

from smena_api.core.tokens import TokenError, issue_access_token, verify_access_token

SECRET = "test-secret-that-is-at-least-32-bytes-long"


def test_issue_then_verify_roundtrip() -> None:
    user_id = uuid.uuid4()
    token = issue_access_token(secret=SECRET, user_id=user_id, ttl_seconds=60)
    claims = verify_access_token(secret=SECRET, token=token)
    assert claims.user_id == user_id


def test_wrong_secret_is_rejected() -> None:
    token = issue_access_token(secret=SECRET, user_id=uuid.uuid4(), ttl_seconds=60)
    with pytest.raises(TokenError):
        verify_access_token(secret="other-secret", token=token)


def test_expired_token_is_rejected() -> None:
    token = issue_access_token(secret=SECRET, user_id=uuid.uuid4(), ttl_seconds=-10)
    with pytest.raises(TokenError):
        verify_access_token(secret=SECRET, token=token)


def test_alg_none_forgery_is_rejected() -> None:
    # Classic JWT attack: unsigned token with attacker-chosen subject.
    forged = jwt.encode(
        {"sub": str(uuid.uuid4()), "typ": "smena-access", "exp": int(time.time()) + 300},
        "",
        algorithm="none",
    )
    with pytest.raises(TokenError):
        verify_access_token(secret=SECRET, token=forged)


def test_foreign_token_type_is_rejected() -> None:
    # Correctly signed but not an access token: type confusion must fail.
    payload = {
        "sub": str(uuid.uuid4()),
        "typ": "password-reset",
        "exp": int(time.time()) + 300,
    }
    forged = jwt.encode(payload, SECRET, algorithm="HS256")
    with pytest.raises(TokenError):
        verify_access_token(secret=SECRET, token=forged)

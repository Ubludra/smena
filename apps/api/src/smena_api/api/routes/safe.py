"""Safe unlock: a second factor between the raw access token and protected data.

Honest scope (product rule: no crypto promises we don't keep):

* the factor is a dedicated SAFE PASSWORD — knowledge, not possession. There
  is no SMS channel (that needs a paid provider this deployment does not
  have) and no recovery channel: a forgotten password means the Safe simply
  stays closed until the account owner resets it server-side;
* only a scrypt hash of the password is stored (random salt, constant-time
  compare) — the plaintext never reaches the database or the logs;
* the unlock is a short-lived (minutes) JWT with a distinct token type, sent
  as ``X-Safe-Token``. Protected listings and protected detail reads require
  it; without it they answer 403. A stolen access token alone no longer
  opens the Safe;
* «Заблокировать» forgets the token client-side; server-side the token simply
  expires (stateless by design, the bound is documented above).
"""

import datetime as dt
import hashlib
import hmac
import secrets
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from smena_api.api.deps import get_app_settings, get_current_user, get_session
from smena_api.core.tokens import TokenError, issue_safe_token, verify_safe_token
from smena_api.db.models import User
from smena_api.schemas.safe import SafeStatusOut, SafeUnlockIn, SafeUnlockOut

router = APIRouter(prefix="/safe", tags=["safe"])

SAFE_HEADER = "X-Safe-Token"
_SAFE_TTL_SECONDS = 15 * 60

SessionDep = Annotated[AsyncSession, Depends(get_session)]
UserDep = Annotated[User, Depends(get_current_user)]

# scrypt cost tuned for a login-adjacent check: ~50-100 ms server-side,
# brutal for offline cracking, harmless at this request rate.
_SCRYPT_N = 2**14
_SCRYPT_R = 8
_SCRYPT_P = 1
_SALT_BYTES = 16
_HASH_BYTES = 32


def hash_safe_password(password: str) -> str:
    """Self-describing scrypt digest: scrypt$N$r$p$salt_hex$hash_hex."""
    salt = secrets.token_bytes(_SALT_BYTES)
    digest = hashlib.scrypt(
        password.encode(), salt=salt, n=_SCRYPT_N, r=_SCRYPT_R, p=_SCRYPT_P,
        dklen=_HASH_BYTES,
    )
    return f"scrypt${_SCRYPT_N}${_SCRYPT_R}${_SCRYPT_P}${salt.hex()}${digest.hex()}"


def verify_safe_password(password: str, stored: str) -> bool:
    """Constant-time compare; malformed/foreign formats never match."""
    parts = stored.split("$")
    if len(parts) != 6 or parts[0] != "scrypt":
        return False
    try:
        n, r, p = (int(parts[1]), int(parts[2]), int(parts[3]))
        salt = bytes.fromhex(parts[4])
        expected = bytes.fromhex(parts[5])
    except ValueError:
        return False
    if n < 2 or (n & (n - 1)) != 0 or r < 1 or p < 1 or not salt or not expected:
        return False
    digest = hashlib.scrypt(
        password.encode(), salt=salt, n=n, r=r, p=p, dklen=len(expected)
    )
    return hmac.compare_digest(digest, expected)


async def check_safe_password_attempt(
    *, password: str, user: User, session: AsyncSession
) -> bool:
    """Persistent rate limit shared by unlock and passkey enrollment.

    Call only after acquiring a FOR UPDATE lock on the user row.
    """
    now = dt.datetime.now(dt.UTC)
    if user.safe_auth_blocked_until is not None and user.safe_auth_blocked_until > now:
        raise HTTPException(429, "Слишком много попыток. Повторите через 15 минут")
    if user.safe_password_hash is None or not verify_safe_password(
        password, user.safe_password_hash
    ):
        user.safe_auth_failures += 1
        if user.safe_auth_failures >= 5:
            user.safe_auth_failures = 0
            user.safe_auth_blocked_until = now + dt.timedelta(minutes=15)
        await session.commit()
        return False
    if user.safe_auth_failures or user.safe_auth_blocked_until is not None:
        user.safe_auth_failures = 0
        user.safe_auth_blocked_until = None
        await session.commit()
    return True


def require_safe_unlock(request: Request, user: User) -> None:
    """Raise 403 unless the request carries a fresh Safe unlock for THIS user.

    Called by every route that reveals protected content (Сейф listings and
    protected material/assessment details).
    """
    token = request.headers.get(SAFE_HEADER)
    settings = get_app_settings(request)
    if token is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Сейф заблокирован"
        )
    try:
        claims = verify_safe_token(
            secret=settings.secret_key.get_secret_value(), token=token
        )
    except TokenError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Сейф заблокирован"
        ) from None
    if claims.user_id != user.id or claims.safe_version != user.safe_password_version:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Сейф заблокирован"
        )


@router.get("/status", response_model=SafeStatusOut)
async def safe_status(user: UserDep) -> SafeStatusOut:
    return SafeStatusOut(has_password=user.safe_password_hash is not None)


@router.post("/unlock", response_model=SafeUnlockOut)
async def unlock(
    body: SafeUnlockIn, user: UserDep, session: SessionDep, request: Request
) -> SafeUnlockOut:
    user = (
        await session.execute(select(User).where(User.id == user.id).with_for_update())
    ).scalar_one()
    if user.safe_password_hash is None:
        # First run sets the password (documented flow: the Safe page
        # explains this before the first submit).
        user.safe_password_hash = hash_safe_password(body.password)
        await session.commit()
        await session.refresh(user)
    elif not await check_safe_password_attempt(
        password=body.password, user=user, session=session
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Пароль не совпадает с установленным для Сейфа",
        )
    settings = get_app_settings(request)
    token = issue_safe_token(
        secret=settings.secret_key.get_secret_value(),
        user_id=user.id,
        ttl_seconds=_SAFE_TTL_SECONDS,
        safe_version=user.safe_password_version,
    )
    return SafeUnlockOut(token=token, expires_in_seconds=_SAFE_TTL_SECONDS)

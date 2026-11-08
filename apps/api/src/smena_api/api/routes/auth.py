"""Authentication endpoints.

Two identity sources exist by design (product spec §22–23):

* ``POST /auth/max-launch`` — production path: the signed ``WebApp.initData``
  from the MAX mini-app is verified server-side with the official algorithm
  (integrations/max_auth.py). Without ``MAX_BOT_TOKEN`` the endpoint honestly
  reports 503 MAX_NOT_CONFIGURED.
* ``POST /auth/dev-login`` — development fallback, disabled by configuration
  and refused by the settings validator in production (fail-closed).

The frontend is untrusted in both cases: identity is established server-side
only, and every subsequent request authenticates via the signed token.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from smena_api.api.deps import get_current_user, get_session
from smena_api.config import Settings
from smena_api.core.tokens import issue_access_token
from smena_api.db.models import User
from smena_api.integrations.max_auth import (
    MaxInvalidData,
    MaxNotConfigured,
    MaxStaleData,
    verify_launch_context,
)
from smena_api.schemas.auth import (
    DevLoginRequest,
    MaxLaunchRequest,
    TokenResponse,
    UserOut,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])


def _issue_token(*, user: User, settings: Settings) -> str:
    """Issue a session token; unwrap the signing secret at exactly one place."""
    signing_secret = settings.secret_key.get_secret_value()
    return issue_access_token(
        secret=signing_secret,
        user_id=user.id,
        ttl_seconds=settings.access_token_ttl_seconds,
    )


@router.post(
    "/max-launch",
    response_model=TokenResponse,
    summary="Exchange MAX launch data (WebApp.initData) for an access token",
)
async def max_launch(
    body: MaxLaunchRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> TokenResponse:
    """Production login: verify the signed MAX launch context server-side.

    Implements the official validation algorithm
    (https://dev.max.ru/docs/webapps/validation). Honest states:

    * 503 ``MAX_NOT_CONFIGURED`` — deployment has no ``MAX_BOT_TOKEN``,
      verification is impossible; never bypassed.
    * 401 ``MAX_INVALID_LAUNCH_DATA`` — forged/corrupted/stale payload.
    """
    settings: Settings = request.app.state.settings
    try:
        identity = verify_launch_context(body.init_data, settings)
    except MaxNotConfigured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "MAX_NOT_CONFIGURED",
                "message": "MAX-интеграция не настроена: серверу нужен токен бота",
            },
        ) from None
    except (MaxInvalidData, MaxStaleData):
        # No details about *why* the payload failed: signature-failure
        # diagnostics are an oracle for attackers. Log, don't tell.
        logger.info("max_launch_rejected")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "code": "MAX_INVALID_LAUNCH_DATA",
                "message": "Не удалось проверить данные запуска MAX",
            },
        ) from None

    user = (
        await session.execute(select(User).where(User.max_user_id == identity.max_user_id))
    ).scalar_one_or_none()
    if user is None:
        user = User(max_user_id=identity.max_user_id, display_name=identity.display_name)
        session.add(user)
        try:
            await session.commit()
        except IntegrityError:  # concurrent first launch
            await session.rollback()
            user = (
                await session.execute(select(User).where(User.max_user_id == identity.max_user_id))
            ).scalar_one()
    elif user.display_name != identity.display_name:
        # Keep the greeting in the UI in sync with the platform profile.
        user.display_name = identity.display_name
        await session.commit()
    await session.refresh(user)

    token = _issue_token(user=user, settings=settings)
    return TokenResponse(access_token=token, user=UserOut.model_validate(user))


@router.post("/dev-login", response_model=TokenResponse)
async def dev_login(
    body: DevLoginRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> TokenResponse:
    """Development-only login: get-or-create the teacher by display name.

    404 (not 403) when disabled, so a production mistake doesn't announce
    the endpoint's existence.
    """
    settings: Settings = request.app.state.settings
    if not settings.enable_dev_auth:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    # Namespaced synthetic identity keeps dev users in the same unique column
    # as real MAX identities without colliding with them.
    max_user_id = f"dev:{body.display_name.lower()}"
    user = (
        await session.execute(select(User).where(User.max_user_id == max_user_id))
    ).scalar_one_or_none()
    if user is None:
        user = User(max_user_id=max_user_id, display_name=body.display_name)
        session.add(user)
        try:
            await session.commit()
        except IntegrityError:
            # Concurrent first login of the same handle: lose the race,
            # re-read the winner.
            await session.rollback()
            user = (
                await session.execute(select(User).where(User.max_user_id == max_user_id))
            ).scalar_one()
        await session.refresh(user)

    token = _issue_token(user=user, settings=settings)
    return TokenResponse(access_token=token, user=UserOut.model_validate(user))


@router.get("/me", response_model=UserOut)
async def me(user: User = Depends(get_current_user)) -> UserOut:
    return UserOut.model_validate(user)

"""Shared FastAPI dependencies."""

from collections.abc import AsyncIterator

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from smena_api.config import Settings
from smena_api.core.tokens import TokenError, verify_access_token
from smena_api.db.models import User
from smena_api.db.session import Database


def get_database(request: Request) -> Database:
    """Return the process-wide Database owned by the app lifespan."""
    db: Database = request.app.state.db
    return db


def get_app_settings(request: Request) -> Settings:
    """Return the settings the app was created with."""
    settings: Settings = request.app.state.settings
    return settings


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    """Yield a per-request AsyncSession (closed automatically)."""
    async with get_database(request).session_factory() as session:
        yield session


# auto_error=False: we raise our own 401 with WWW-Authenticate below.
_bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    session: AsyncSession = Depends(get_session),
) -> User:
    """Resolve the authenticated user from a Bearer token.

    The client is untrusted: the token signature is verified against the
    server secret, and the user row is re-read from the database — a token
    for a deleted user stops working immediately.
    """
    if credentials is None:
        raise _unauthorized()
    settings = get_app_settings(request)
    try:
        claims = verify_access_token(
            secret=settings.secret_key.get_secret_value(), token=credentials.credentials
        )
    except TokenError:
        raise _unauthorized() from None

    # Full-row load on purpose: the row is tiny and the login/me routes need
    # display_name; defer-loading it would explode under async lazy-load.
    stmt = select(User).where(User.id == claims.user_id)
    user = (await session.execute(stmt)).scalar_one_or_none()
    if user is None:
        raise _unauthorized()
    return user


def _unauthorized() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Требуется вход",
        headers={"WWW-Authenticate": "Bearer"},
    )

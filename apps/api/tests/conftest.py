"""Shared pytest fixtures: isolated test database + app + HTTP client.

Strategy: everything is function-scoped. Each test gets its own engine on a
freshly recreated ``public`` schema of the dedicated test database
(``smena_test`` by default, from TEST_DATABASE_URL). The database itself is
created once if missing. Function scope avoids asyncpg event-loop binding
pitfalls and gives full isolation at negligible cost for this schema size.
"""

import os
import re
import shutil
import tempfile
from collections.abc import AsyncIterator, Callable

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

import smena_api.db.models  # noqa: F401  (registers all tables on metadata)
from smena_api.config import Settings
from smena_api.db.base import Base
from smena_api.main import create_app

_DB_NAME_RE = re.compile(r"^[a-z_][a-z0-9_]*$")


def _temporary_upload_dir() -> str:
    """Create a private temp dir for uploads (cleaned up at process exit)."""
    import atexit

    directory = tempfile.mkdtemp(prefix="smena-uploads-")
    atexit.register(shutil.rmtree, directory, True)
    return directory


def _test_database_url() -> str:
    url = os.environ.get("TEST_DATABASE_URL")
    if url:
        return url
    main_url = os.environ.get(
        "DATABASE_URL",
        "postgresql+asyncpg://smena:smena_dev_only@localhost:5432/smena",
    )
    return main_url.rsplit("/", 1)[0] + "/smena_test"


def _maintenance_url(test_url: str) -> tuple[str, str]:
    base, _, db_name = test_url.rpartition("/")
    if not _DB_NAME_RE.match(db_name):
        raise ValueError(f"unsafe test database name: {db_name!r}")
    return base + "/postgres", db_name


async def _ensure_test_database(maintenance_url: str, db_name: str) -> None:
    admin_engine = create_async_engine(maintenance_url, isolation_level="AUTOCOMMIT")
    try:
        async with admin_engine.connect() as conn:
            exists = await conn.scalar(
                text("SELECT 1 FROM pg_database WHERE datname = :name"),
                {"name": db_name},
            )
            if not exists:
                # db_name is validated against _DB_NAME_RE before use.
                await conn.execute(text(f'CREATE DATABASE "{db_name}"'))
    finally:
        await admin_engine.dispose()


@pytest.fixture
async def db_engine() -> AsyncIterator[AsyncEngine]:
    test_url = _test_database_url()
    maintenance_url, db_name = _maintenance_url(test_url)
    await _ensure_test_database(maintenance_url, db_name)

    engine = create_async_engine(test_url)
    async with engine.begin() as conn:
        await conn.execute(text("DROP SCHEMA public CASCADE"))
        await conn.execute(text("CREATE SCHEMA public"))
        await conn.run_sync(Base.metadata.create_all)
        # Migrations never run here; seed the built-in system templates the
        # same way production's seed migration does (idempotent, same rows).
        from smena_api.services.builtin_reports import seed_builtin

        await conn.run_sync(seed_builtin)
    yield engine
    await engine.dispose()


@pytest.fixture
async def db_session(db_engine: AsyncEngine) -> AsyncIterator[AsyncSession]:
    factory = async_sessionmaker(db_engine, expire_on_commit=False)
    async with factory() as session:
        yield session


@pytest.fixture
def app_factory(db_engine: AsyncEngine) -> Callable[..., FastAPI]:
    """Build configured app instances sharing the test schema.

    ``db_engine`` establishes it before any app is created. Tests that need
    non-default settings (e.g. MAX_BOT_TOKEN) get their own app through this
    factory while still using the same database.
    """

    def factory(**overrides: object) -> FastAPI:
        # Pin the default app to "MAX not configured": the developer's real
        # .env must not flip MAX-dependent tests between 503/401. Tests that
        # need a token pass max_bot_token=... via overrides.
        overrides.setdefault("max_bot_token", None)
        # Uploads go to a throwaway directory per app instance — never to the
        # real /data/uploads mount, and blobs are cleaned up after the run.
        if "upload_dir" not in overrides:
            overrides["upload_dir"] = str(_temporary_upload_dir())
        settings = Settings(  # type: ignore[call-arg]
            environment="test",
            database_url=_test_database_url(),
            secret_key="unit-test-secret-key-not-for-production",
            api_host="127.0.0.1",
            log_level="WARNING",
            **overrides,
        )
        return create_app(settings)

    return factory


@pytest.fixture
async def app(app_factory: Callable[..., FastAPI]) -> AsyncIterator[FastAPI]:
    application = app_factory()
    async with application.router.lifespan_context(application):
        yield application


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac

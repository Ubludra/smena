"""Async engine and session management.

The ``Database`` object is created once per application run (in the FastAPI
lifespan) and stored on ``app.state``; per-request sessions come from its
``session_factory`` via the ``get_session`` dependency (api/deps.py).
"""

import logging

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

logger = logging.getLogger(__name__)


class Database:
    """Owns the async engine and the session factory."""

    def __init__(self, url: str, *, echo: bool = False) -> None:
        self.engine: AsyncEngine = create_async_engine(
            url,
            echo=echo,
            pool_pre_ping=True,
        )
        self.session_factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
            self.engine, expire_on_commit=False
        )

    async def check(self) -> None:
        """Raise if the database is not reachable/usable."""
        async with self.engine.connect() as connection:
            await connection.execute(text("SELECT 1"))

    async def dispose(self) -> None:
        await self.engine.dispose()
        logger.info("database_engine_disposed")

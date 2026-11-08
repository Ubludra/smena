"""Application factory.

``create_app`` builds a fully configured FastAPI instance from explicit
settings, which keeps the app testable (tests inject their own Settings)
and avoids import-time side effects beyond the module-level ``app`` used
by ``uvicorn smena_api.main:app``.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from smena_api import __version__
from smena_api.api.routes.assessments import router as assessments_router
from smena_api.api.routes.assignments import router as assignments_router
from smena_api.api.routes.auth import router as auth_router
from smena_api.api.routes.calendar import router as calendar_router
from smena_api.api.routes.files import router as files_router
from smena_api.api.routes.health import router as health_router
from smena_api.api.routes.lesson_plans import router as lesson_plans_router
from smena_api.api.routes.materials import router as materials_router
from smena_api.api.routes.report_chat import router as report_chat_router
from smena_api.api.routes.report_docs import router as report_docs_router
from smena_api.api.routes.reports import router as reports_router
from smena_api.api.routes.safe import router as safe_router
from smena_api.api.routes.safe_security import router as safe_security_router
from smena_api.api.routes.templates import router as templates_router
from smena_api.config import Settings, get_settings
from smena_api.core.logging import configure_logging
from smena_api.db.session import Database

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

logger = logging.getLogger(__name__)

API_V1_PREFIX = "/api/v1"


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        database = Database(settings.database_url.get_secret_value())
        app.state.db = database
        app.state.settings = settings
        logger.info(
            "api_startup",
            extra={"environment": settings.environment, "version": __version__},
        )
        try:
            yield
        finally:
            await database.dispose()
            logger.info("api_shutdown")

    is_production = settings.environment == "production"
    app = FastAPI(
        title="Смена — API преподавателя",
        version=__version__,
        lifespan=lifespan,
        # Interactive API docs are a development aid only; in production
        # they are disabled to reduce the attack surface.
        docs_url=None if is_production else "/docs",
        redoc_url=None,
        openapi_url=None if is_production else "/openapi.json",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        # Bearer-token auth needs no credentialed CORS; keeping credentials
        # off removes a whole class of CSRF-adjacent mistakes.
        allow_credentials=False,
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Request-Id"],
        expose_headers=["X-Request-Id"],
        max_age=600,
    )
    # Probes live at the root (orchestrator convention); the product API is
    # versioned under /api/v1.
    app.include_router(health_router)
    app.include_router(auth_router, prefix=API_V1_PREFIX)
    app.include_router(materials_router, prefix=API_V1_PREFIX)
    app.include_router(lesson_plans_router, prefix=API_V1_PREFIX)
    app.include_router(assignments_router, prefix=API_V1_PREFIX)
    app.include_router(assessments_router, prefix=API_V1_PREFIX)
    app.include_router(templates_router, prefix=API_V1_PREFIX)
    app.include_router(reports_router, prefix=API_V1_PREFIX)
    # Report documents share the /reports prefix: keep them AFTER reports_router
    # so its literal paths (e.g. /reports/summary) match before /reports/{id}.
    app.include_router(report_docs_router, prefix=API_V1_PREFIX)
    app.include_router(report_chat_router, prefix=API_V1_PREFIX)
    app.include_router(safe_router, prefix=API_V1_PREFIX)
    app.include_router(safe_security_router, prefix=API_V1_PREFIX)
    app.include_router(files_router, prefix=API_V1_PREFIX)
    app.include_router(calendar_router, prefix=API_V1_PREFIX)
    return app


app = create_app()

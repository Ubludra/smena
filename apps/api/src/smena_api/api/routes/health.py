"""Liveness and readiness probes.

/health/live  — process is up (no dependency checks; safe behind any
                orchestrator).
/health/ready — application can actually serve requests: database reachable;
                503 otherwise. Deliberately reveals nothing about internals
                beyond a boolean.
"""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, Response
from sqlalchemy.exc import SQLAlchemyError

from smena_api.api.deps import get_database
from smena_api.db.session import Database
from smena_api.schemas.health import HealthResponse, NotReadyResponse, ReadyResponse

logger = logging.getLogger(__name__)

router = APIRouter(tags=["system"])

DatabaseDep = Annotated[Database, Depends(get_database)]


@router.get("/health/live", response_model=HealthResponse)
async def health_live() -> HealthResponse:
    return HealthResponse(status="ok")


@router.get(
    "/health/ready",
    response_model=ReadyResponse,
    responses={503: {"model": NotReadyResponse}},
)
async def health_ready(
    response: Response,
    database: DatabaseDep,
) -> ReadyResponse | NotReadyResponse:
    try:
        await database.check()
    except SQLAlchemyError as exc:
        # Log only the exception class: connection errors can embed the DSN
        # (with credentials). Never log the exception message itself here.
        logger.warning("readiness_probe_failed error=%s", type(exc).__name__)
        response.status_code = 503
        return NotReadyResponse(status="unavailable", database="error")
    return ReadyResponse(status="ready", database="ok")

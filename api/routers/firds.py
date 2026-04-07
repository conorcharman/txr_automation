"""
FIRDS Router
============

REST endpoints for triggering FIRDS (Financial Instruments Reference Data System)
reportability scripts as background jobs.

Endpoints:
    GET  /api/firds/scripts    — List registered FIRDS script names
    POST /api/firds/refresh    — Refresh the local FIRDS SQLite cache
    POST /api/firds/check      — Check reportability of one or more ISINs
    POST /api/firds/backfill   — Backfill FIRDS reportability across a directory of files
"""

import logging

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from api.database import get_db
from api.schemas.firds import FirdsBackfillRequest, FirdsCheckRequest, FirdsRefreshRequest
from api.schemas.jobs import JobResponse
from api.services.job_service import job_service
from api.services.script_runner import script_runner_service
from api.tasks.script_tasks import run_script

logger = logging.getLogger(__name__)

router = APIRouter(tags=["firds"])

_FIRDS_SCRIPTS: list[str] = sorted(
    [
        "firds_backfill",
        "firds_check",
        "firds_refresh",
    ]
)


@router.get("/firds/scripts", response_model=list[str])
async def list_firds_scripts() -> list[str]:
    """Return a sorted list of all registered FIRDS script names.

    Returns:
        Alphabetically sorted list of FIRDS script name strings.
    """
    return _FIRDS_SCRIPTS


@router.post("/firds/refresh", response_model=JobResponse)
async def firds_refresh(
    body: FirdsRefreshRequest,
    db: AsyncSession = Depends(get_db),
) -> JobResponse:
    """Refresh the local FIRDS SQLite cache as a background Celery job.

    Args:
        body: Validated ``FirdsRefreshRequest`` from the request body.
        db: Async database session injected by FastAPI.

    Returns:
        A ``JobResponse`` for the newly created pending job.
    """
    module_path, argv, config_snapshot = script_runner_service.build_firds_argv(
        body, "firds_refresh"
    )
    job = await job_service.create_job(db, "firds_refresh", config_snapshot)

    run_script.delay(str(job.id), module_path, argv, config_snapshot)
    logger.info("Dispatched FIRDS refresh task for job %s.", job.id)

    return JobResponse.from_orm_job(job)


@router.post("/firds/check", response_model=JobResponse)
async def firds_check(
    body: FirdsCheckRequest,
    db: AsyncSession = Depends(get_db),
) -> JobResponse:
    """Check FIRDS reportability for one or more ISINs as a background Celery job.

    Args:
        body: Validated ``FirdsCheckRequest`` from the request body.
        db: Async database session injected by FastAPI.

    Returns:
        A ``JobResponse`` for the newly created pending job.
    """
    module_path, argv, config_snapshot = script_runner_service.build_firds_argv(
        body, "firds_check"
    )
    job = await job_service.create_job(db, "firds_check", config_snapshot)

    run_script.delay(str(job.id), module_path, argv, config_snapshot)
    logger.info("Dispatched FIRDS check task for job %s.", job.id)

    return JobResponse.from_orm_job(job)


@router.post("/firds/backfill", response_model=JobResponse)
async def firds_backfill(
    body: FirdsBackfillRequest,
    db: AsyncSession = Depends(get_db),
) -> JobResponse:
    """Backfill FIRDS reportability across a directory of files as a background Celery job.

    Args:
        body: Validated ``FirdsBackfillRequest`` from the request body.
        db: Async database session injected by FastAPI.

    Returns:
        A ``JobResponse`` for the newly created pending job.
    """
    module_path, argv, config_snapshot = script_runner_service.build_firds_argv(
        body, "firds_backfill"
    )
    job = await job_service.create_job(db, "firds_backfill", config_snapshot)

    run_script.delay(str(job.id), module_path, argv, config_snapshot)
    logger.info("Dispatched FIRDS backfill task for job %s.", job.id)

    return JobResponse.from_orm_job(job)

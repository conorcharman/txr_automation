"""
GLEIF Router
============

REST endpoints for triggering GLEIF (Global Legal Entity Identifier Foundation)
LEI lookup scripts as background jobs.

Endpoints:
    GET  /api/gleif/scripts    — List registered GLEIF script names
    POST /api/gleif/refresh    — Refresh the local GLEIF SQLite cache
    POST /api/gleif/check      — Look up LEI data for one or more entities
    POST /api/gleif/backfill   — Backfill GLEIF LEI data across a directory of files
"""

import logging
from datetime import date as date_type

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from api.database import get_db
from api.schemas.gleif import (
    GleifBackfillRequest,
    GleifCheckRequest,
    GleifLookupResponse,
    GleifRefreshRequest,
    GleifSearchResponse,
    GleifSearchResult,
)
from api.schemas.jobs import JobResponse
from api.services.job_service import job_service
from api.services.lookup import gleif_lookup_service
from api.services.script_runner import script_runner_service
from api.tasks.script_tasks import run_script

logger = logging.getLogger(__name__)

router = APIRouter(tags=["gleif"])

_GLEIF_SCRIPTS: list[str] = sorted(
    [
        "gleif_backfill",
        "gleif_check",
        "gleif_refresh",
    ]
)


@router.get("/gleif/scripts", response_model=list[str])
async def list_gleif_scripts() -> list[str]:
    """Return a sorted list of all registered GLEIF script names.

    Returns:
        Alphabetically sorted list of GLEIF script name strings.
    """
    return _GLEIF_SCRIPTS


@router.get("/gleif/lookup", response_model=GleifLookupResponse)
async def gleif_lookup(
    lei: str,
    date: str | None = None,
) -> GleifLookupResponse:
    """Look up a single LEI from the local GLEIF cache synchronously.

    Args:
        lei: The LEI code to look up.
        date: Optional trade date in ``YYYY-MM-DD`` format.

    Returns:
        A ``GleifLookupResponse`` with the full LEI record.
    """
    trade_date = date_type.fromisoformat(date) if date else None
    result = gleif_lookup_service.lookup_lei(lei, trade_date)
    return GleifLookupResponse(**result)


@router.get("/gleif/search", response_model=GleifSearchResponse)
async def gleif_search(
    name: str,
    limit: int = 20,
) -> GleifSearchResponse:
    """Search for legal entities by name in the local GLEIF cache.

    Args:
        name: Company name to search for (supports partial matching).
        limit: Maximum number of results to return (default: 20).

    Returns:
        A ``GleifSearchResponse`` with the matching entities.
    """
    raw_results = gleif_lookup_service.search_by_name(name, limit=limit)
    results = [
        GleifSearchResult(
            lei=r.get("lei", ""),
            legal_name=r.get("legal_name", ""),
            status=r.get("registration_status", r.get("status", "")),
            country=r.get("legal_address_country", r.get("country", "")),
        )
        for r in raw_results
    ]
    return GleifSearchResponse(results=results, count=len(results))


@router.post("/gleif/refresh", response_model=JobResponse)
async def gleif_refresh(
    body: GleifRefreshRequest,
    db: AsyncSession = Depends(get_db),
) -> JobResponse:
    """Refresh the local GLEIF SQLite cache as a background Celery job.

    A full refresh downloads the GLEIF Golden Copy and rebuilds the local
    SQLite database.  A delta refresh applies incremental updates.

    Args:
        body: Validated ``GleifRefreshRequest`` from the request body.
        db: Async database session injected by FastAPI.

    Returns:
        A ``JobResponse`` for the newly created pending job.
    """
    module_path, argv, config_snapshot = script_runner_service.build_gleif_argv(
        body, "gleif_refresh"
    )
    job = await job_service.create_job(db, "gleif_refresh", config_snapshot)

    run_script.delay(str(job.id), module_path, argv, config_snapshot)
    logger.info("Dispatched GLEIF refresh task for job %s.", job.id)

    return JobResponse.from_orm_job(job)


@router.post("/gleif/check", response_model=JobResponse)
async def gleif_check(
    body: GleifCheckRequest,
    db: AsyncSession = Depends(get_db),
) -> JobResponse:
    """Look up GLEIF LEI data for one or more entities as a background Celery job.

    Supports single LEI lookup, name search, and batch CSV processing.

    Args:
        body: Validated ``GleifCheckRequest`` from the request body.
        db: Async database session injected by FastAPI.

    Returns:
        A ``JobResponse`` for the newly created pending job.
    """
    module_path, argv, config_snapshot = script_runner_service.build_gleif_argv(
        body, "gleif_check"
    )
    job = await job_service.create_job(db, "gleif_check", config_snapshot)

    run_script.delay(str(job.id), module_path, argv, config_snapshot)
    logger.info("Dispatched GLEIF check task for job %s.", job.id)

    return JobResponse.from_orm_job(job)


@router.post("/gleif/backfill", response_model=JobResponse)
async def gleif_backfill(
    body: GleifBackfillRequest,
    db: AsyncSession = Depends(get_db),
) -> JobResponse:
    """Backfill GLEIF LEI data across a directory of files as a background Celery job.

    Args:
        body: Validated ``GleifBackfillRequest`` from the request body.
        db: Async database session injected by FastAPI.

    Returns:
        A ``JobResponse`` for the newly created pending job.
    """
    module_path, argv, config_snapshot = script_runner_service.build_gleif_argv(
        body, "gleif_backfill"
    )
    job = await job_service.create_job(db, "gleif_backfill", config_snapshot)

    run_script.delay(str(job.id), module_path, argv, config_snapshot)
    logger.info("Dispatched GLEIF backfill task for job %s.", job.id)

    return JobResponse.from_orm_job(job)

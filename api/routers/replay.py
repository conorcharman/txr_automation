"""
Replay Router
=============

REST endpoints for triggering replay processing scripts as background jobs.

Endpoints:
    GET  /api/replay/scripts       — List registered replay script names
    POST /api/replay/phase2        — Run the Phase 2 replay processor
    POST /api/replay/phase3        — Run the Phase 3 replay processor
    POST /api/replay/phase3-final  — Run the Phase 3 final lookup processor
    POST /api/replay/merge         — Merge Phase 3 Inconsistent ID summary files
"""

import logging

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from api.database import get_db
from api.schemas.jobs import JobResponse
from api.schemas.replay import (
    ReplayMergeRequest,
    ReplayPhase2Request,
    ReplayPhase3FinalRequest,
    ReplayPhase3Request,
)
from api.services.job_service import job_service
from api.services.script_runner import script_runner_service
from api.tasks.script_tasks import run_script

logger = logging.getLogger(__name__)

router = APIRouter(tags=["replay"])

_REPLAY_SCRIPTS: list[str] = sorted(
    [
        "replay_merge_inconsistent",
        "replay_phase2",
        "replay_phase3",
        "replay_phase3_final",
    ]
)


@router.get("/replay/scripts", response_model=list[str])
async def list_replay_scripts() -> list[str]:
    """Return a sorted list of all registered replay script names.

    Returns:
        Alphabetically sorted list of replay script name strings.
    """
    return _REPLAY_SCRIPTS


@router.post("/replay/phase2", response_model=JobResponse)
async def run_replay_phase2(
    body: ReplayPhase2Request,
    db: AsyncSession = Depends(get_db),
) -> JobResponse:
    """Run the Phase 2 replay processor as a background Celery job.

    Phase 2 applies validated corrections from Kaizen incident template files
    to the corresponding replay CSV files.

    Args:
        body: Validated ``ReplayPhase2Request`` from the request body.
        db: Async database session injected by FastAPI.

    Returns:
        A ``JobResponse`` for the newly created pending job.
    """
    module_path, argv, config_snapshot = script_runner_service.build_replay_argv(
        body, "replay_phase2"
    )
    job = await job_service.create_job(db, "replay_phase2", config_snapshot)

    run_script.delay(str(job.id), module_path, argv, config_snapshot)
    logger.info("Dispatched replay phase2 task for job %s.", job.id)

    return JobResponse.from_orm_job(job)


@router.post("/replay/phase3", response_model=JobResponse)
async def run_replay_phase3(
    body: ReplayPhase3Request,
    db: AsyncSession = Depends(get_db),
) -> JobResponse:
    """Run the Phase 3 replay processor as a background Celery job.

    Phase 3 processes Inconsistent ID and Name summary files, applying
    corrections from incident template files.

    Args:
        body: Validated ``ReplayPhase3Request`` from the request body.
        db: Async database session injected by FastAPI.

    Returns:
        A ``JobResponse`` for the newly created pending job.
    """
    module_path, argv, config_snapshot = script_runner_service.build_replay_argv(
        body, "replay_phase3"
    )
    job = await job_service.create_job(db, "replay_phase3", config_snapshot)

    run_script.delay(str(job.id), module_path, argv, config_snapshot)
    logger.info("Dispatched replay phase3 task for job %s.", job.id)

    return JobResponse.from_orm_job(job)


@router.post("/replay/phase3-final", response_model=JobResponse)
async def run_replay_phase3_final(
    body: ReplayPhase3FinalRequest,
    db: AsyncSession = Depends(get_db),
) -> JobResponse:
    """Run the Phase 3 final lookup processor as a background Celery job.

    Phase 3 final lookup matches Phase 3 Inconsistent summary records against
    UnaVista reference data to resolve remaining corrections.

    Args:
        body: Validated ``ReplayPhase3FinalRequest`` from the request body.
        db: Async database session injected by FastAPI.

    Returns:
        A ``JobResponse`` for the newly created pending job.
    """
    module_path, argv, config_snapshot = script_runner_service.build_replay_argv(
        body, "replay_phase3_final"
    )
    job = await job_service.create_job(db, "replay_phase3_final", config_snapshot)

    run_script.delay(str(job.id), module_path, argv, config_snapshot)
    logger.info("Dispatched replay phase3-final task for job %s.", job.id)

    return JobResponse.from_orm_job(job)


@router.post("/replay/merge", response_model=JobResponse)
async def run_replay_merge(
    body: ReplayMergeRequest,
    db: AsyncSession = Depends(get_db),
) -> JobResponse:
    """Merge Phase 3 Inconsistent ID and Name summary files as a background Celery job.

    Args:
        body: Validated ``ReplayMergeRequest`` from the request body.
        db: Async database session injected by FastAPI.

    Returns:
        A ``JobResponse`` for the newly created pending job.
    """
    module_path, argv, config_snapshot = script_runner_service.build_replay_argv(
        body, "replay_merge_inconsistent"
    )
    job = await job_service.create_job(db, "replay_merge_inconsistent", config_snapshot)

    run_script.delay(str(job.id), module_path, argv, config_snapshot)
    logger.info("Dispatched replay merge task for job %s.", job.id)

    return JobResponse.from_orm_job(job)

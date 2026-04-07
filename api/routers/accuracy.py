"""
Accuracy Testing Router
=======================

REST endpoints for triggering accuracy validation scripts as background jobs.

Endpoints:
    GET  /api/accuracy/scripts    — List all registered accuracy validation script names
    POST /api/accuracy/run        — Run a single accuracy validation script
    POST /api/accuracy/run-all    — Run the run_all_validations orchestrator
"""

import logging

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from api.database import get_db
from api.schemas.accuracy import RunAllRequest, RunValidationRequest
from api.schemas.jobs import JobResponse
from api.services.job_service import job_service
from api.services.script_runner import ACCURACY_VALIDATION_SCRIPTS, script_runner_service
from api.tasks.script_tasks import run_script

logger = logging.getLogger(__name__)

router = APIRouter(tags=["accuracy"])

_ACCURACY_SCRIPTS: list[str] = sorted(ACCURACY_VALIDATION_SCRIPTS)


@router.get("/accuracy/scripts", response_model=list[str])
async def list_accuracy_scripts() -> list[str]:
    """Return a sorted list of all registered accuracy validation script names.

    Returns:
        Alphabetically sorted list of script name strings accepted by
        ``POST /api/accuracy/run``.
    """
    return _ACCURACY_SCRIPTS


@router.post("/accuracy/run", response_model=JobResponse)
async def run_validation(
    body: RunValidationRequest,
    db: AsyncSession = Depends(get_db),
) -> JobResponse:
    """Run a single accuracy validation script as a background Celery job.

    The script configuration is serialised to a temporary YAML file by the
    ``ScriptRunnerService`` and the task is dispatched immediately.  The caller
    can poll ``GET /api/jobs/{id}`` or subscribe to the WebSocket log stream
    to monitor progress.

    Args:
        body: Validated ``RunValidationRequest`` from the request body.
        db: Async database session injected by FastAPI.

    Returns:
        A ``JobResponse`` for the newly created pending job.

    Raises:
        HTTPException: 400 if ``script_name`` is not a valid accuracy script.
    """
    module_path, argv, config_snapshot = script_runner_service.build_accuracy_argv(body)
    job = await job_service.create_job(db, body.script_name, config_snapshot)

    run_script.delay(str(job.id), module_path, argv, config_snapshot)
    logger.info(
        "Dispatched accuracy validation task for job %s (script=%s).",
        job.id,
        body.script_name,
    )

    return JobResponse.from_orm_job(job)


@router.post("/accuracy/run-all", response_model=JobResponse)
async def run_all_validations(
    body: RunAllRequest,
    db: AsyncSession = Depends(get_db),
) -> JobResponse:
    """Run the run_all_validations orchestrator as a background Celery job.

    Generates individual batch configs for each requested validation type and
    dispatches the orchestrator script, which runs them sequentially and
    aggregates results.

    Args:
        body: Validated ``RunAllRequest`` from the request body.
        db: Async database session injected by FastAPI.

    Returns:
        A ``JobResponse`` for the newly created pending job.
    """
    module_path, argv, config_snapshot = script_runner_service.build_run_all_argv(body)
    job = await job_service.create_job(db, "run_all_validations", config_snapshot)

    run_script.delay(str(job.id), module_path, argv, config_snapshot)
    logger.info(
        "Dispatched run_all_validations task for job %s (%d validation type(s)).",
        job.id,
        len(body.validation_types),
    )

    return JobResponse.from_orm_job(job)

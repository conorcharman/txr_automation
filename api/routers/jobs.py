"""
Jobs Router
===========

REST endpoints for managing background job records, plus a WebSocket
endpoint for streaming live log output to connected clients.

Endpoints:
    GET  /api/jobs                    — List jobs (paginated)
    GET  /api/jobs/{job_id}           — Retrieve a single job
    POST /api/jobs                    — Create a job and dispatch a Celery task
    POST /api/jobs/{job_id}/cancel    — Cancel a pending or running job
    WS   /api/ws/jobs/{job_id}/logs   — Stream live logs via Redis pub/sub

The ``SCRIPT_MODULES`` dict maps a registered ``script_name`` string to
its fully-qualified Python module path.  Extend this dict in Phase 4 as
more scripts are migrated from the GUI.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, WebSocket
from sqlalchemy.ext.asyncio import AsyncSession

from api.database import get_db
from api.schemas.common import JobStatus
from api.schemas.jobs import JobCreate, JobResponse
from api.services.job_service import job_service
from api.tasks.script_tasks import run_script
from api.websocket.log_stream import log_stream_ws

logger = logging.getLogger(__name__)

router = APIRouter(tags=["jobs"])

# ---------------------------------------------------------------------------
# Script registry
# ---------------------------------------------------------------------------

#: Maps registered script name identifiers to their Python module paths.
#: The module at each path must expose a ``main(argv: list[str]) -> None``
#: function following the established CLI entry-point pattern.
SCRIPT_MODULES: dict[str, str] = {
    "buyer_id_validation": "src.accuracy_testing.scripts.buyer_id_validation",
    "seller_id_validation": "src.accuracy_testing.scripts.seller_id_validation",
    # Phase 4 will extend this dict with all remaining scripts.
}


def _resolve_module(script_name: str) -> str:
    """Return the module path for a registered script name.

    Args:
        script_name: The registered identifier, e.g. ``"buyer_id_validation"``.

    Returns:
        The dotted Python module path string.

    Raises:
        HTTPException: 400 if the script name is not registered.
    """
    module_path = SCRIPT_MODULES.get(script_name)
    if module_path is None:
        registered = sorted(SCRIPT_MODULES.keys())
        raise HTTPException(
            status_code=400,
            detail=(
                f"Unknown script '{script_name}'. "
                f"Registered scripts: {registered}"
            ),
        )
    return module_path


# ---------------------------------------------------------------------------
# REST routes
# ---------------------------------------------------------------------------


@router.get("/jobs", response_model=list[JobResponse])
async def list_jobs(
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
) -> list[JobResponse]:
    """Return a paginated list of jobs, most recent first.

    Args:
        limit: Maximum number of jobs to return (default 50).
        offset: Number of jobs to skip for pagination (default 0).
        db: Async database session injected by FastAPI.

    Returns:
        A list of ``JobResponse`` objects.
    """
    jobs = await job_service.list_jobs(db, limit=limit, offset=offset)
    return [JobResponse.from_orm_job(j) for j in jobs]


@router.get("/jobs/{job_id}", response_model=JobResponse)
async def get_job(
    job_id: str,
    db: AsyncSession = Depends(get_db),
) -> JobResponse:
    """Retrieve a single job by its UUID.

    Args:
        job_id: String UUID of the job to retrieve.
        db: Async database session injected by FastAPI.

    Returns:
        The ``JobResponse`` for the requested job.

    Raises:
        HTTPException: 404 if no job with the given UUID exists.
    """
    job = await job_service.get_job(db, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found.")
    return JobResponse.from_orm_job(job)


@router.post("/jobs", response_model=JobResponse)
async def create_job(
    body: JobCreate,
    db: AsyncSession = Depends(get_db),
) -> JobResponse:
    """Create a new job row and dispatch the corresponding Celery task.

    The job is created in ``pending`` status before the task is dispatched,
    so the client immediately receives a job ID that can be polled or
    subscribed to via the WebSocket endpoint.

    Args:
        body: Request body containing ``script_name`` and ``config``.
        db: Async database session injected by FastAPI.

    Returns:
        The ``JobResponse`` for the newly created job.

    Raises:
        HTTPException: 400 if the ``script_name`` is not registered.
    """
    module_path = _resolve_module(body.script_name)
    job = await job_service.create_job(db, body.script_name, body.config)

    # Build argv from config; for now pass an empty list — Phase 4 will
    # derive argv from config fields per-script.
    argv: list[str] = []

    run_script.delay(
        str(job.id),
        module_path,
        argv,
        body.config,
    )
    logger.info(
        "Dispatched task for job %s (script=%s).", job.id, body.script_name
    )

    return JobResponse.from_orm_job(job)


@router.post("/jobs/{job_id}/cancel", response_model=JobResponse)
async def cancel_job(
    job_id: str,
    db: AsyncSession = Depends(get_db),
) -> JobResponse:
    """Cancel a job by setting its status to ``cancelled``.

    This is a best-effort operation: the Celery task may have already
    finished or may not respond to cancellation.  The database record is
    updated regardless.

    Args:
        job_id: String UUID of the job to cancel.
        db: Async database session injected by FastAPI.

    Returns:
        The updated ``JobResponse``.

    Raises:
        HTTPException: 404 if no job with the given UUID exists.
    """
    job = await job_service.get_job(db, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found.")

    if job.status in (JobStatus.SUCCESS, JobStatus.FAILED, JobStatus.CANCELLED):
        # Already in a terminal state; return as-is without updating.
        return JobResponse.from_orm_job(job)

    await job_service.update_status(db, job_id, "cancelled")
    updated_job = await job_service.get_job(db, job_id)
    assert updated_job is not None  # noqa: S101 — just fetched above
    return JobResponse.from_orm_job(updated_job)


# ---------------------------------------------------------------------------
# WebSocket route — registered directly on the router so it is included
# under the /api prefix in main.py.
# ---------------------------------------------------------------------------


@router.websocket("/ws/jobs/{job_id}/logs")
async def ws_job_logs(websocket: WebSocket, job_id: str) -> None:
    """Stream live log output for a job over WebSocket.

    Delegates to ``log_stream_ws``, which subscribes to the Redis
    ``job:{job_id}:logs`` pub/sub channel and forwards messages until
    the client disconnects or the channel is exhausted.

    Args:
        websocket: The active WebSocket connection.
        job_id: UUID string of the job whose logs to stream.
    """
    await log_stream_ws(websocket, job_id)

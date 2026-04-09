"""
Scheduler Router
================

REST endpoints for managing scheduled pipeline runs.

Endpoints:
    GET    /api/schedules              — List all schedules
    POST   /api/schedules              — Create a new schedule
    GET    /api/schedules/{id}         — Retrieve a single schedule
    PUT    /api/schedules/{id}         — Update a schedule
    DELETE /api/schedules/{id}         — Delete a schedule
    POST   /api/schedules/{id}/trigger — Manually trigger a schedule
    POST   /api/schedules/{id}/toggle  — Enable or disable a schedule
"""

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from api.database import get_db
from api.routers.jobs import SCRIPT_MODULES
from api.schemas.schedule import (
    ScheduleCreate,
    ScheduleResponse,
    ScheduleTriggerResponse,
    ScheduleUpdate,
    _VALID_FREQUENCIES,
)
from api.services.job_service import job_service
from api.services.schedule_service import schedule_service
from api.tasks.script_tasks import run_script

logger = logging.getLogger(__name__)

router = APIRouter(tags=["scheduler"])


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------


def _validate_create(body: ScheduleCreate) -> None:
    """Validate the fields of a ``ScheduleCreate`` request.

    Args:
        body: The incoming create request.

    Raises:
        HTTPException: 400 if any field is invalid.
    """
    if body.frequency not in _VALID_FREQUENCIES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid frequency '{body.frequency}'. "
            f"Must be one of: {sorted(_VALID_FREQUENCIES)}.",
        )
    if body.frequency == "custom" and not body.cron_expression:
        raise HTTPException(
            status_code=400,
            detail="cron_expression is required when frequency is 'custom'.",
        )
    if body.script_name not in SCRIPT_MODULES:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown script '{body.script_name}'.",
        )


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("/schedules", response_model=list[ScheduleResponse])
async def list_schedules(
    db: AsyncSession = Depends(get_db),
) -> list[ScheduleResponse]:
    """Return all schedules ordered by name.

    Args:
        db: Async database session injected by FastAPI.

    Returns:
        A list of ``ScheduleResponse`` objects.
    """
    schedules = await schedule_service.list_schedules(db)
    return [ScheduleResponse.from_orm_schedule(s) for s in schedules]


@router.post("/schedules", response_model=ScheduleResponse, status_code=201)
async def create_schedule(
    body: ScheduleCreate,
    db: AsyncSession = Depends(get_db),
) -> ScheduleResponse:
    """Create a new schedule.

    The ``next_run_at`` timestamp is calculated automatically based on the
    chosen frequency.

    Args:
        body: Request body with schedule configuration.
        db: Async database session injected by FastAPI.

    Returns:
        The newly created ``ScheduleResponse``.

    Raises:
        HTTPException: 400 if the frequency or script name is invalid.
        HTTPException: 409 if a schedule with the same name already exists.
    """
    _validate_create(body)

    try:
        schedule = await schedule_service.create_schedule(
            db,
            name=body.name,
            script_name=body.script_name,
            frequency=body.frequency,
            cron_expression=body.cron_expression,
            config_data=body.config_data,
            is_active=body.is_active,
        )
    except Exception as exc:
        err = str(exc)
        if "unique" in err.lower() or "duplicate" in err.lower():
            raise HTTPException(
                status_code=409,
                detail=f"A schedule named '{body.name}' already exists.",
            ) from exc
        raise HTTPException(status_code=400, detail=err) from exc

    return ScheduleResponse.from_orm_schedule(schedule)


@router.get("/schedules/{schedule_id}", response_model=ScheduleResponse)
async def get_schedule(
    schedule_id: str,
    db: AsyncSession = Depends(get_db),
) -> ScheduleResponse:
    """Retrieve a single schedule by its UUID.

    Args:
        schedule_id: String UUID of the schedule.
        db: Async database session injected by FastAPI.

    Returns:
        The matching ``ScheduleResponse``.

    Raises:
        HTTPException: 404 if no schedule with the given UUID exists.
    """
    schedule = await schedule_service.get_schedule(db, schedule_id)
    if schedule is None:
        raise HTTPException(status_code=404, detail="Schedule not found.")
    return ScheduleResponse.from_orm_schedule(schedule)


@router.put("/schedules/{schedule_id}", response_model=ScheduleResponse)
async def update_schedule(
    schedule_id: str,
    body: ScheduleUpdate,
    db: AsyncSession = Depends(get_db),
) -> ScheduleResponse:
    """Update an existing schedule.

    Only fields supplied in the request body are modified.  ``next_run_at``
    is recalculated whenever frequency, cron expression, or active status
    changes.

    Args:
        schedule_id: String UUID of the schedule to update.
        body: Partial update request body.
        db: Async database session injected by FastAPI.

    Returns:
        The updated ``ScheduleResponse``.

    Raises:
        HTTPException: 404 if the schedule does not exist.
        HTTPException: 400 if any updated field is invalid.
    """
    schedule = await schedule_service.get_schedule(db, schedule_id)
    if schedule is None:
        raise HTTPException(status_code=404, detail="Schedule not found.")

    updates = body.model_dump(exclude_none=True)

    if "frequency" in updates and updates["frequency"] not in _VALID_FREQUENCIES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid frequency '{updates['frequency']}'.",
        )
    if "script_name" in updates and updates["script_name"] not in SCRIPT_MODULES:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown script '{updates['script_name']}'.",
        )

    try:
        schedule = await schedule_service.update_schedule(db, schedule, **updates)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return ScheduleResponse.from_orm_schedule(schedule)


@router.delete("/schedules/{schedule_id}", status_code=204)
async def delete_schedule(
    schedule_id: str,
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete a schedule permanently.

    Args:
        schedule_id: String UUID of the schedule to delete.
        db: Async database session injected by FastAPI.

    Raises:
        HTTPException: 404 if the schedule does not exist.
    """
    schedule = await schedule_service.get_schedule(db, schedule_id)
    if schedule is None:
        raise HTTPException(status_code=404, detail="Schedule not found.")
    await schedule_service.delete_schedule(db, schedule)


@router.post("/schedules/{schedule_id}/trigger", response_model=ScheduleTriggerResponse)
async def trigger_schedule(
    schedule_id: str,
    db: AsyncSession = Depends(get_db),
) -> ScheduleTriggerResponse:
    """Manually trigger a schedule, dispatching a Celery job immediately.

    This endpoint fires the schedule's script regardless of whether the
    schedule is active or its ``next_run_at`` has passed.  The schedule's
    ``last_run_at`` and ``next_run_at`` are updated accordingly.

    Args:
        schedule_id: String UUID of the schedule to trigger.
        db: Async database session injected by FastAPI.

    Returns:
        A ``ScheduleTriggerResponse`` containing the new job UUID.

    Raises:
        HTTPException: 404 if the schedule does not exist.
        HTTPException: 400 if the script name is no longer registered.
    """
    schedule = await schedule_service.get_schedule(db, schedule_id)
    if schedule is None:
        raise HTTPException(status_code=404, detail="Schedule not found.")

    module_path = SCRIPT_MODULES.get(schedule.script_name)
    if module_path is None:
        raise HTTPException(
            status_code=400,
            detail=f"Script '{schedule.script_name}' is no longer registered.",
        )

    config = schedule.config_data or {}
    job = await job_service.create_job(db, schedule.script_name, config)

    run_script.delay(
        str(job.id),
        module_path,
        [],
        config,
    )

    await schedule_service.mark_triggered(db, schedule, status="pending")

    return ScheduleTriggerResponse(
        job_id=str(job.id),
        schedule_id=str(schedule.id),
        message=f"Schedule '{schedule.name}' triggered. Job {job.id} dispatched.",
    )


@router.post("/schedules/{schedule_id}/toggle", response_model=ScheduleResponse)
async def toggle_schedule(
    schedule_id: str,
    db: AsyncSession = Depends(get_db),
) -> ScheduleResponse:
    """Toggle a schedule between active and inactive.

    When re-activated, ``next_run_at`` is recalculated from the current time.
    When deactivated, ``next_run_at`` is cleared.

    Args:
        schedule_id: String UUID of the schedule to toggle.
        db: Async database session injected by FastAPI.

    Returns:
        The updated ``ScheduleResponse``.

    Raises:
        HTTPException: 404 if the schedule does not exist.
    """
    schedule = await schedule_service.get_schedule(db, schedule_id)
    if schedule is None:
        raise HTTPException(status_code=404, detail="Schedule not found.")

    updated = await schedule_service.update_schedule(
        db, schedule, is_active=not schedule.is_active
    )
    return ScheduleResponse.from_orm_schedule(updated)

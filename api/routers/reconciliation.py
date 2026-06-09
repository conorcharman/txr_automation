"""
Reconciliation Router
=====================

REST endpoints for managing scheduled reconciliation runs.

Endpoints:
    GET    /api/reconciliations              — List all reconciliation schedules
    POST   /api/reconciliations              — Create a new reconciliation schedule
    GET    /api/reconciliations/{id}         — Retrieve a single schedule
    PUT    /api/reconciliations/{id}         — Update a schedule
    DELETE /api/reconciliations/{id}         — Delete a schedule
    POST   /api/reconciliations/{id}/trigger — Manually trigger a reconciliation
    POST   /api/reconciliations/{id}/toggle  — Enable or disable a schedule
"""

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from api.database import get_db
from api.schemas.reconciliation import (
    RECONCILIATION_SCRIPTS,
    ReconciliationCreate,
    ReconciliationResponse,
    ReconciliationUpdate,
)
from api.schemas.schedule import _VALID_FREQUENCIES
from api.services.job_service import job_service
from api.services.reconciliation_service import reconciliation_service

logger = logging.getLogger(__name__)

router = APIRouter(tags=["reconciliations"])


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------


def _validate_create(body: ReconciliationCreate) -> None:
    """Validate the fields of a ``ReconciliationCreate`` request.

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
    if not body.selected_scripts:
        raise HTTPException(
            status_code=400,
            detail="At least one script must be selected.",
        )
    invalid = set(body.selected_scripts) - RECONCILIATION_SCRIPTS
    if invalid:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid reconciliation scripts: {sorted(invalid)}.",
        )


def _to_response(rec: object) -> ReconciliationResponse:
    """Convert a ReconciliationSchedule ORM instance to a response.

    Args:
        rec: ``ReconciliationSchedule`` ORM instance.

    Returns:
        Serialisable ``ReconciliationResponse``.
    """
    return ReconciliationResponse.model_validate(rec, from_attributes=True)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("/reconciliations", response_model=list[ReconciliationResponse])
async def list_reconciliations(
    db: AsyncSession = Depends(get_db),
) -> list[ReconciliationResponse]:
    """Return all reconciliation schedules ordered by name."""
    recs = await reconciliation_service.list_reconciliations(db)
    return [_to_response(r) for r in recs]


@router.post("/reconciliations", response_model=ReconciliationResponse, status_code=201)
async def create_reconciliation(
    body: ReconciliationCreate,
    db: AsyncSession = Depends(get_db),
) -> ReconciliationResponse:
    """Create a new reconciliation schedule.

    Args:
        body: Request body with reconciliation configuration.
        db: Async database session injected by FastAPI.

    Returns:
        The newly created ``ReconciliationResponse``.

    Raises:
        HTTPException: 400 if validation fails.
        HTTPException: 409 if a schedule with the same name already exists.
    """
    _validate_create(body)

    try:
        rec = await reconciliation_service.create_reconciliation(
            db,
            name=body.name,
            selected_scripts=body.selected_scripts,
            frequency=body.frequency,
            rec_period_days=body.rec_period_days,
            lookback_days=body.lookback_days,
            cron_expression=body.cron_expression,
            config_overrides=body.config_overrides,
            stop_on_error=body.stop_on_error,
            is_active=body.is_active,
        )
    except Exception as exc:
        err = str(exc)
        if "unique" in err.lower() or "duplicate" in err.lower():
            raise HTTPException(
                status_code=409,
                detail=f"A reconciliation named '{body.name}' already exists.",
            ) from exc
        raise HTTPException(status_code=400, detail=err) from exc

    return _to_response(rec)


@router.get("/reconciliations/{rec_id}", response_model=ReconciliationResponse)
async def get_reconciliation(
    rec_id: str,
    db: AsyncSession = Depends(get_db),
) -> ReconciliationResponse:
    """Retrieve a single reconciliation schedule by its UUID."""
    rec = await reconciliation_service.get_reconciliation(db, rec_id)
    if rec is None:
        raise HTTPException(status_code=404, detail="Reconciliation not found.")
    return _to_response(rec)


@router.put("/reconciliations/{rec_id}", response_model=ReconciliationResponse)
async def update_reconciliation(
    rec_id: str,
    body: ReconciliationUpdate,
    db: AsyncSession = Depends(get_db),
) -> ReconciliationResponse:
    """Update an existing reconciliation schedule.

    Only fields supplied in the request body are modified.
    """
    rec = await reconciliation_service.get_reconciliation(db, rec_id)
    if rec is None:
        raise HTTPException(status_code=404, detail="Reconciliation not found.")

    updates = body.model_dump(exclude_none=True)

    if "frequency" in updates and updates["frequency"] not in _VALID_FREQUENCIES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid frequency '{updates['frequency']}'.",
        )
    if "selected_scripts" in updates:
        invalid = set(updates["selected_scripts"]) - RECONCILIATION_SCRIPTS
        if invalid:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid reconciliation scripts: {sorted(invalid)}.",
            )

    updated = await reconciliation_service.update_reconciliation(db, rec, **updates)
    return _to_response(updated)


@router.delete("/reconciliations/{rec_id}", status_code=204)
async def delete_reconciliation(
    rec_id: str,
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete a reconciliation schedule."""
    rec = await reconciliation_service.get_reconciliation(db, rec_id)
    if rec is None:
        raise HTTPException(status_code=404, detail="Reconciliation not found.")
    await reconciliation_service.delete_reconciliation(db, rec)


@router.post("/reconciliations/{rec_id}/trigger")
async def trigger_reconciliation(
    rec_id: str,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Manually trigger a reconciliation run.

    Creates a parent job and dispatches the ``run_reconciliation`` Celery task.

    Args:
        rec_id: String UUID of the reconciliation to trigger.
        db: Async database session injected by FastAPI.

    Returns:
        A dict with the created ``job_id``.

    Raises:
        HTTPException: 404 if the reconciliation does not exist.
    """
    rec = await reconciliation_service.get_reconciliation(db, rec_id)
    if rec is None:
        raise HTTPException(status_code=404, detail="Reconciliation not found.")

    from api.tasks.reconciliation_tasks import run_reconciliation

    config_snapshot = {
        "reconciliation_id": str(rec.id),
        "reconciliation_name": rec.name,
        "rec_period_days": rec.rec_period_days,
        "lookback_days": rec.lookback_days,
        "selected_scripts": rec.selected_scripts,
        "config_overrides": rec.config_overrides,
        "stop_on_error": rec.stop_on_error,
    }

    job = await job_service.create_job(
        db, f"reconciliation:{rec.name}", config_snapshot
    )
    run_reconciliation.delay(str(job.id), config_snapshot)

    await reconciliation_service.mark_triggered(db, rec, status="pending")

    return {"jobId": str(job.id)}


@router.post(
    "/reconciliations/{rec_id}/toggle",
    response_model=ReconciliationResponse,
)
async def toggle_reconciliation(
    rec_id: str,
    db: AsyncSession = Depends(get_db),
) -> ReconciliationResponse:
    """Toggle a reconciliation schedule's active state."""
    rec = await reconciliation_service.get_reconciliation(db, rec_id)
    if rec is None:
        raise HTTPException(status_code=404, detail="Reconciliation not found.")

    updated = await reconciliation_service.update_reconciliation(
        db, rec, is_active=not rec.is_active
    )
    return _to_response(updated)

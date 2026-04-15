"""
Pipeline Router
===============

REST endpoints for managing accuracy testing pipeline schedules.

Endpoints:
    GET    /api/pipelines              — List all pipelines
    POST   /api/pipelines              — Create a new pipeline
    GET    /api/pipelines/{id}         — Retrieve a single pipeline
    PUT    /api/pipelines/{id}         — Update a pipeline
    DELETE /api/pipelines/{id}         — Delete a pipeline
    POST   /api/pipelines/{id}/trigger — Manually trigger a pipeline
    POST   /api/pipelines/{id}/toggle  — Enable or disable a pipeline
"""

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from api.database import get_db
from api.schemas.pipeline import PipelineCreate, PipelineResponse, PipelineUpdate
from api.schemas.schedule import _VALID_FREQUENCIES
from api.services.pipeline_service import pipeline_service
from api.services.job_service import job_service

logger = logging.getLogger(__name__)

router = APIRouter(tags=["pipelines"])

#: Script keys that are valid for inclusion in an accuracy testing pipeline.
PIPELINE_SCRIPTS: frozenset[str] = frozenset(
    {
        "sql_extract_generator",
        "accuracy_template_generator",
        "collate_csv_extracts",
        "buyer_id_validation",
        "seller_id_validation",
        "inconsistent_buyer_id_validation",
        "inconsistent_seller_id_validation",
        "validate_ftbdm",
        "validate_ftsdm",
        "incorrect_net_amount_validation",
        "non_zero_net_quantity",
        "non_zero_net_amount",
        "data_push",
    }
)


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------


def _validate_create(body: PipelineCreate) -> None:
    """Validate the fields of a ``PipelineCreate`` request.

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
    invalid = set(body.selected_scripts) - PIPELINE_SCRIPTS
    if invalid:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid pipeline scripts: {sorted(invalid)}.",
        )


def _to_response(pipeline: object) -> PipelineResponse:
    """Convert a Pipeline ORM instance to a PipelineResponse.

    Args:
        pipeline: ``Pipeline`` ORM instance.

    Returns:
        Serialisable ``PipelineResponse``.
    """
    return PipelineResponse.model_validate(pipeline, from_attributes=True)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("/pipelines", response_model=list[PipelineResponse])
async def list_pipelines(
    db: AsyncSession = Depends(get_db),
) -> list[PipelineResponse]:
    """Return all pipelines ordered by name.

    Args:
        db: Async database session injected by FastAPI.

    Returns:
        A list of ``PipelineResponse`` objects.
    """
    pipelines = await pipeline_service.list_pipelines(db)
    return [_to_response(p) for p in pipelines]


@router.post("/pipelines", response_model=PipelineResponse, status_code=201)
async def create_pipeline(
    body: PipelineCreate,
    db: AsyncSession = Depends(get_db),
) -> PipelineResponse:
    """Create a new pipeline.

    The ``next_run_at`` timestamp is calculated automatically based on the
    chosen frequency.

    Args:
        body: Request body with pipeline configuration.
        db: Async database session injected by FastAPI.

    Returns:
        The newly created ``PipelineResponse``.

    Raises:
        HTTPException: 400 if validation fails.
        HTTPException: 409 if a pipeline with the same name already exists.
    """
    _validate_create(body)

    try:
        pipeline = await pipeline_service.create_pipeline(
            db,
            name=body.name,
            fiscal_year=body.fiscal_year,
            quarter=body.quarter,
            selected_scripts=body.selected_scripts,
            frequency=body.frequency,
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
                detail=f"A pipeline named '{body.name}' already exists.",
            ) from exc
        raise HTTPException(status_code=400, detail=err) from exc

    return _to_response(pipeline)


@router.get("/pipelines/{pipeline_id}", response_model=PipelineResponse)
async def get_pipeline(
    pipeline_id: str,
    db: AsyncSession = Depends(get_db),
) -> PipelineResponse:
    """Retrieve a single pipeline by its UUID.

    Args:
        pipeline_id: String UUID of the pipeline.
        db: Async database session injected by FastAPI.

    Returns:
        The matching ``PipelineResponse``.

    Raises:
        HTTPException: 404 if no pipeline with the given UUID exists.
    """
    pipeline = await pipeline_service.get_pipeline(db, pipeline_id)
    if pipeline is None:
        raise HTTPException(status_code=404, detail="Pipeline not found.")
    return _to_response(pipeline)


@router.put("/pipelines/{pipeline_id}", response_model=PipelineResponse)
async def update_pipeline(
    pipeline_id: str,
    body: PipelineUpdate,
    db: AsyncSession = Depends(get_db),
) -> PipelineResponse:
    """Update an existing pipeline.

    Only fields supplied in the request body are modified.  ``next_run_at``
    is recalculated whenever frequency, cron expression, or active status
    changes.

    Args:
        pipeline_id: String UUID of the pipeline to update.
        body: Partial update request body.
        db: Async database session injected by FastAPI.

    Returns:
        The updated ``PipelineResponse``.

    Raises:
        HTTPException: 404 if the pipeline does not exist.
        HTTPException: 400 if any updated field is invalid.
    """
    pipeline = await pipeline_service.get_pipeline(db, pipeline_id)
    if pipeline is None:
        raise HTTPException(status_code=404, detail="Pipeline not found.")

    updates = body.model_dump(exclude_none=True)

    if "frequency" in updates and updates["frequency"] not in _VALID_FREQUENCIES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid frequency '{updates['frequency']}'.",
        )
    if "selected_scripts" in updates:
        invalid = set(updates["selected_scripts"]) - PIPELINE_SCRIPTS
        if invalid:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid pipeline scripts: {sorted(invalid)}.",
            )

    updated = await pipeline_service.update_pipeline(db, pipeline, **updates)
    return _to_response(updated)


@router.delete("/pipelines/{pipeline_id}", status_code=204)
async def delete_pipeline(
    pipeline_id: str,
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete a pipeline.

    Args:
        pipeline_id: String UUID of the pipeline to delete.
        db: Async database session injected by FastAPI.

    Raises:
        HTTPException: 404 if the pipeline does not exist.
    """
    pipeline = await pipeline_service.get_pipeline(db, pipeline_id)
    if pipeline is None:
        raise HTTPException(status_code=404, detail="Pipeline not found.")
    await pipeline_service.delete_pipeline(db, pipeline)


@router.post("/pipelines/{pipeline_id}/trigger")
async def trigger_pipeline(
    pipeline_id: str,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Manually trigger a pipeline run.

    Creates a parent job and dispatches the ``run_pipeline`` Celery task.

    Args:
        pipeline_id: String UUID of the pipeline to trigger.
        db: Async database session injected by FastAPI.

    Returns:
        A dict with the created ``job_id``.

    Raises:
        HTTPException: 404 if the pipeline does not exist.
    """
    pipeline = await pipeline_service.get_pipeline(db, pipeline_id)
    if pipeline is None:
        raise HTTPException(status_code=404, detail="Pipeline not found.")

    from api.tasks.pipeline_tasks import run_pipeline

    # For quarterly pipelines, auto-calculate the fiscal period.
    fiscal_year = pipeline.fiscal_year
    quarter = pipeline.quarter
    if pipeline.frequency == "quarterly":
        from api.utils.fiscal_date import get_completed_quarter
        from datetime import datetime, timezone

        fiscal_year, quarter = get_completed_quarter(
            datetime.now(tz=timezone.utc)
        )

    config_snapshot = {
        "pipeline_id": str(pipeline.id),
        "pipeline_name": pipeline.name,
        "fiscal_year": fiscal_year,
        "quarter": quarter,
        "selected_scripts": pipeline.selected_scripts,
        "config_overrides": pipeline.config_overrides,
        "stop_on_error": pipeline.stop_on_error,
    }

    job = await job_service.create_job(
        db, f"pipeline:{pipeline.name}", config_snapshot
    )
    run_pipeline.delay(str(job.id), config_snapshot)

    await pipeline_service.mark_triggered(db, pipeline, status="pending")

    return {"jobId": str(job.id)}


@router.post("/pipelines/{pipeline_id}/toggle", response_model=PipelineResponse)
async def toggle_pipeline(
    pipeline_id: str,
    db: AsyncSession = Depends(get_db),
) -> PipelineResponse:
    """Toggle a pipeline's active state.

    Args:
        pipeline_id: String UUID of the pipeline to toggle.
        db: Async database session injected by FastAPI.

    Returns:
        The updated ``PipelineResponse`` with the new ``is_active`` value.

    Raises:
        HTTPException: 404 if the pipeline does not exist.
    """
    pipeline = await pipeline_service.get_pipeline(db, pipeline_id)
    if pipeline is None:
        raise HTTPException(status_code=404, detail="Pipeline not found.")

    updated = await pipeline_service.update_pipeline(
        db, pipeline, is_active=not pipeline.is_active
    )
    return _to_response(updated)

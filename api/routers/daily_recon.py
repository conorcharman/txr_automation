"""
Daily Reconciliation Router
===========================

FastAPI router for /api/daily-recon/* endpoints.
Thin async route handlers; delegates to service layer.
"""

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from api.database import get_db
from api.models.daily_recon import ReconCell, ReconRow
from api.schemas.daily_recon import (
    CellCorrectionRequest,
    CellResponse,
    DailyReconTriggerRequest,
    PaginatedRowsResponse,
    PaginatedRunsResponse,
    RowResponse,
    RunDetailResponse,
    RunResponse,
)
from api.services.daily_recon_service import daily_recon_service

router = APIRouter(prefix="/daily-recon", tags=["daily-recon"])


# ────────────────────────────────────────────────────────────────────────────
# Runs Management
# ────────────────────────────────────────────────────────────────────────────


@router.get("/runs", response_model=PaginatedRunsResponse)
async def list_runs(
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """List all daily reconciliation runs (paginated).

    Args:
        limit: Max rows per page.
        offset: Rows to skip.
        db: Database session.

    Returns:
        Paginated list of runs.
    """
    runs = await daily_recon_service.list_runs(db, limit=limit, offset=offset)
    return {
        "data": [RunResponse.model_validate(run) for run in runs],
        "total": len(runs),  # TODO: proper count query
        "limit": limit,
        "offset": offset,
    }


@router.get("/runs/{run_id}", response_model=RunDetailResponse)
async def get_run(
    run_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Fetch a single run with all rows and cells.

    Args:
        run_id: Run UUID.
        db: Database session.

    Returns:
        RunDetailResponse with nested rows/cells.

    Raises:
        404: If run not found.
    """
    run = await daily_recon_service.get_run(db, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    return RunDetailResponse.model_validate(run)


@router.post("/runs", response_model=RunResponse, status_code=201)
async def trigger_run(
    req: DailyReconTriggerRequest,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Trigger a new daily reconciliation run (queues Celery task).

    If no ``source_query`` is supplied, the stored canonical query is used.

    Args:
        req: Request body with optional sourceQuery override.
        db: Database session.

    Returns:
        Created RunResponse.

    Note:
        The Celery task is dispatched asynchronously; this returns immediately.
        The actual extraction/validation happens in the background.
    """
    from api.daily_recon.source_query import DAILY_RECON_QUERY
    from api.services.job_service import job_service
    from api.tasks.daily_recon_tasks import run_daily_recon

    query = req.source_query or DAILY_RECON_QUERY

    # Create a job so the run shows up in job history / log streaming.
    job = await job_service.create_job(db, "daily_recon", {"source": "sql_server"})

    run = await daily_recon_service.create_run(
        db,
        job_id=job.id,
        source_query=query,
    )

    # Dispatch the background extraction + validation + persistence task.
    run_daily_recon.delay(str(job.id), str(run.id), query)

    return RunResponse.model_validate(run)


# ────────────────────────────────────────────────────────────────────────────
# Rows Management
# ────────────────────────────────────────────────────────────────────────────


@router.get("/runs/{run_id}/rows", response_model=PaginatedRowsResponse)
async def list_rows(
    run_id: UUID,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    errored_only: bool = Query(False),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """List rows in a run (optionally filtered by error status).

    Args:
        run_id: Run UUID.
        limit: Max rows per page.
        offset: Rows to skip.
        errored_only: If true, only return rows with errors.
        db: Database session.

    Returns:
        Paginated list of rows.

    Raises:
        404: If run not found.
    """
    run = await daily_recon_service.get_run(db, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    rows = await daily_recon_service.list_rows(
        db,
        run_id=run_id,
        limit=limit,
        offset=offset,
        errored_only=errored_only,
    )
    return {
        "data": [RowResponse.model_validate(row) for row in rows],
        "total": len(rows),  # TODO: proper count query
        "limit": limit,
        "offset": offset,
    }


@router.get("/rows/{row_id}", response_model=RowResponse)
async def get_row(
    row_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Fetch a single row with all cells and issues.

    Args:
        row_id: Row UUID.
        db: Database session.

    Returns:
        RowResponse with nested cells.

    Raises:
        404: If row not found.
    """
    row = await daily_recon_service.get_row(db, row_id)
    if not row:
        raise HTTPException(status_code=404, detail="Row not found")
    return RowResponse.model_validate(row)


# ────────────────────────────────────────────────────────────────────────────
# Row Approval
# ────────────────────────────────────────────────────────────────────────────


@router.post("/rows/{row_id}/approve", response_model=RowResponse)
async def approve_row(
    row_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Mark a row as approved (user acceptance).

    Args:
        row_id: Row UUID.
        db: Database session.

    Returns:
        Updated RowResponse.

    Raises:
        404: If row not found.
    """
    row = await daily_recon_service.approve_row(db, row_id)
    if not row:
        raise HTTPException(status_code=404, detail="Row not found")
    return RowResponse.model_validate(row)


@router.post("/rows/{row_id}/unapprove", response_model=RowResponse)
async def unapprove_row(
    row_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Unmark a row as approved.

    Args:
        row_id: Row UUID.
        db: Database session.

    Returns:
        Updated RowResponse.

    Raises:
        404: If row not found.
    """
    row = await daily_recon_service.unapprove_row(db, row_id)
    if not row:
        raise HTTPException(status_code=404, detail="Row not found")
    return RowResponse.model_validate(row)


# ────────────────────────────────────────────────────────────────────────────
# Cell Corrections
# ────────────────────────────────────────────────────────────────────────────


@router.get("/cells/{cell_id}", response_model=CellResponse)
async def get_cell(
    cell_id: int,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Fetch a single cell with issues.

    Args:
        cell_id: Cell ID (bigint).
        db: Database session.

    Returns:
        CellResponse with nested issues.

    Raises:
        404: If cell not found.
    """
    cell = await daily_recon_service.get_cell(db, cell_id)
    if not cell:
        raise HTTPException(status_code=404, detail="Cell not found")
    return CellResponse.model_validate(cell)


@router.patch("/cells/{cell_id}/correct", response_model=CellResponse)
async def apply_correction(
    cell_id: int,
    req: CellCorrectionRequest,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Apply a manual correction to a cell.

    User-edited corrected_value; does not auto-approve the row.

    Args:
        cell_id: Cell ID (bigint).
        req: Request body with corrected_value.
        db: Database session.

    Returns:
        Updated CellResponse.

    Raises:
        404: If cell not found.
    """
    cell = await daily_recon_service.apply_correction(
        db, cell_id, req.corrected_value
    )
    if not cell:
        raise HTTPException(status_code=404, detail="Cell not found")
    return CellResponse.model_validate(cell)


@router.post("/cells/{cell_id}/accept-suggestion", response_model=CellResponse)
async def accept_suggestion(
    cell_id: int,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Accept a suggested fix for a cell.

    Copies suggested_fix → corrected_value. Does not auto-approve.

    Args:
        cell_id: Cell ID (bigint).
        db: Database session.

    Returns:
        Updated CellResponse.

    Raises:
        404: If cell not found or no suggestion available.
    """
    cell = await daily_recon_service.accept_suggestion(db, cell_id)
    if not cell:
        raise HTTPException(
            status_code=404,
            detail="Cell not found or no suggestion available",
        )
    return CellResponse.model_validate(cell)


# ────────────────────────────────────────────────────────────────────────────
# Export
# ────────────────────────────────────────────────────────────────────────────


@router.get("/runs/{run_id}/export")
async def export_run(
    run_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Export approved rows as CSV.

    Returns a streaming CSV response. Includes only approved rows;
    uses corrected_value if present, else original_value.

    Args:
        run_id: Run UUID.
        db: Database session.

    Returns:
        FileResponse with CSV content.

    Raises:
        404: If run not found.

    Note:
        Implementation in next phase (below is skeleton).
    """
    run = await daily_recon_service.get_run(db, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    # TODO: Implement CSV export
    #  - Query approved rows
    #  - Build CSV with column headers from COLUMN_NAMES
    #  - Use value precedence: corrected_value > original_value
    #  - Stream response

    return {"status": "export not yet implemented"}



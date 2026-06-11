"""
Daily Reconciliation Tasks
==========================

Celery task that executes a daily reconciliation POC run:
extract from SQL Server -> validate -> persist rows/cells/issues into
PostgreSQL, publishing progress to Redis (same pattern as
``reconciliation_tasks``).
"""

import asyncio
import json
import logging
from uuid import UUID

import redis as redis_lib
from celery import Task

from api.config import get_settings
from api.daily_recon.columns import COLUMN_NAMES
from api.daily_recon.model import ReconRecord
from api.daily_recon.validation.engine import validate_batch
from api.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


async def _persist_async(
    run_id: str,
    rows: list[dict[str, object]],
) -> tuple[int, int]:
    """Validate and persist extracted rows into PostgreSQL.

    Args:
        run_id: The parent ReconRun UUID string.
        rows: Extracted row dicts keyed by canonical column name.

    Returns:
        Tuple of (total_rows, error_rows).
    """
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from api.models.daily_recon import (
        ReconCell,
        ReconCellIssue,
        ReconRow,
        ReconRun,
    )

    settings = get_settings()
    engine = create_async_engine(settings.database_url, echo=False)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    # Build raw string dicts for validation + persistence.
    records = [ReconRecord.from_row(r) for r in rows]
    raw_batch = [rec.raw for rec in records]
    validation = validate_batch(raw_batch)

    error_row_count = 0
    try:
        async with session_factory() as session:
            for idx, (record, cell_results) in enumerate(
                zip(records, validation)
            ):
                results_by_col = {c.column_name: c for c in cell_results}
                row_has_error = any(c.is_errored for c in cell_results)
                if row_has_error:
                    error_row_count += 1

                row = ReconRow(
                    run_id=UUID(run_id),
                    row_index=idx,
                    trade_ref=record.raw.get("TRADEREF"),
                    has_error=row_has_error,
                )
                session.add(row)
                await session.flush()  # Get row.id for cells.

                for column_name in COLUMN_NAMES:
                    result = results_by_col.get(column_name)
                    is_errored = bool(result and result.is_errored)
                    suggested = result.suggested_fix if result else None

                    cell = ReconCell(
                        row_id=row.id,
                        column_name=column_name,
                        original_value=record.raw.get(column_name),
                        suggested_fix=suggested,
                        is_errored=is_errored,
                    )
                    session.add(cell)
                    await session.flush()  # Get cell.id for issues.

                    if result and result.issues:
                        for issue in result.issues:
                            session.add(
                                ReconCellIssue(
                                    cell_id=cell.id,
                                    rule_id=issue.rule_id,
                                    message=issue.message,
                                    suggested_fix=issue.suggested_fix,
                                )
                            )

            # Update run aggregates.
            run = await session.get(ReconRun, UUID(run_id))
            if run is not None:
                run.row_count = len(records)
                run.error_row_count = error_row_count
                run.status = "validated"

            await session.commit()
    finally:
        await engine.dispose()

    return len(records), error_row_count


async def _update_run_status_async(run_id: str, status: str) -> None:
    """Set the run status (used for running/failed transitions)."""
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from api.models.daily_recon import ReconRun

    settings = get_settings()
    engine = create_async_engine(settings.database_url, echo=False)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with session_factory() as session:
            run = await session.get(ReconRun, UUID(run_id))
            if run is not None:
                run.status = status
                await session.commit()
    finally:
        await engine.dispose()


async def _update_job_status_async(
    job_id: str,
    status: str,
    error_message: str | None = None,
) -> None:
    """Update the linked job's status."""
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from api.services.job_service import job_service

    settings = get_settings()
    engine = create_async_engine(settings.database_url, echo=False)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with session_factory() as session:
            await job_service.update_status(
                session, job_id, status, error_message=error_message
            )
    finally:
        await engine.dispose()


@celery_app.task(bind=True, name="api.tasks.daily_recon_tasks.run_daily_recon")
def run_daily_recon(
    self: Task,
    job_id: str,
    run_id: str,
    query: str | None = None,
) -> dict[str, object]:
    """Extract, validate, and persist a daily reconciliation run.

    Args:
        job_id: UUID string of the parent job.
        run_id: UUID string of the ReconRun row.
        query: Optional SQL override; defaults to the stored query.

    Returns:
        Dict with ``status``, ``rowCount``, and ``errorRowCount``.
    """
    settings = get_settings()
    redis_client = redis_lib.from_url(settings.redis_url)
    channel = f"job:{job_id}:logs"

    def _publish(message: dict) -> None:
        try:
            redis_client.publish(channel, json.dumps(message))
        except Exception as exc:  # noqa: BLE001
            logger.warning("Redis publish failed for job %s: %s", job_id, exc)

    _publish({"type": "status", "data": "running"})
    _publish({"type": "progress", "data": 5})
    asyncio.run(_update_job_status_async(job_id, "running"))
    asyncio.run(_update_run_status_async(run_id, "running"))

    try:
        # Import here so the API process can run without pyodbc installed.
        from api.services.daily_recon_source import extract_rows

        _publish({"type": "log", "data": "Connecting to SQL Server source..."})
        rows = extract_rows(query)
        _publish({"type": "log", "data": f"Extracted {len(rows)} rows."})
        _publish({"type": "progress", "data": 50})

        total, errors = asyncio.run(_persist_async(run_id, rows))
        _publish(
            {
                "type": "log",
                "data": f"Persisted {total} rows ({errors} with errors).",
            }
        )
        _publish({"type": "progress", "data": 100})
        _publish({"type": "status", "data": "success"})
        asyncio.run(_update_job_status_async(job_id, "success"))

        return {"status": "success", "rowCount": total, "errorRowCount": errors}

    except Exception as exc:  # noqa: BLE001
        error_msg = f"Daily reconciliation failed: {exc}"
        logger.exception(error_msg)
        _publish({"type": "log", "data": error_msg})
        _publish({"type": "status", "data": "failed"})
        _publish({"type": "progress", "data": 100})
        asyncio.run(_update_run_status_async(run_id, "failed"))
        asyncio.run(_update_job_status_async(job_id, "failed", error_message=error_msg))
        return {"status": "failed", "error": str(exc)}


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

# Batch size for revalidation — process rows in chunks of 200 to avoid
# memory overload and asyncpg's 32767 parameter limit on selectin() queries.
_REVALIDATE_BATCH_SIZE = 200


async def _is_cancel_requested(run_id: str, redis_client: object) -> bool:
    """Check if a cancellation has been requested for this run via Redis flag.

    Args:
        run_id: The ReconRun UUID string.
        redis_client: Redis client instance (passed in to avoid creating new connections).

    Returns:
        True if cancellation flag is set, False otherwise.
    """
    try:
        flag = redis_client.get(f"revalidate:{run_id}:cancel")  # type: ignore
        return flag is not None
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to check cancellation flag for run %s: %s", run_id, exc)
        return False


class CancellationRequested(Exception):
    """Raised when a revalidation cancellation is requested."""

    pass


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


async def _revalidate_async(run_id: str, redis_client: object) -> tuple[int, int]:
    """Re-validate an existing run by re-running validation on stored rows.

    Uses batched keyset pagination to avoid O(n²) offset scans and memory overload.
    Processes rows in chunks of 200 using row_index-based keyset pagination.
    For each batch:
    1. Load rows + cells + issues via selectinload (no cartesian explosion)
    2. Re-run validation
    3. Diff against stored state — only write changes
    4. Commit batch (safe to retry from last successful batch on failure)

    Args:
        run_id: The parent ReconRun UUID string.
        redis_client: Redis client instance (passed in to avoid creating new connections).

    Returns:
        Tuple of (total_rows, error_rows).
    """
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
    from sqlalchemy.orm import selectinload

    from api.models.daily_recon import (
        ReconCell,
        ReconCellIssue,
        ReconRow,
        ReconRun,
    )

    settings = get_settings()
    engine = create_async_engine(settings.database_url, echo=False)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    total_rows = 0
    error_row_count = 0
    last_row_index = -1  # Keyset pagination marker; start from row_index > -1

    try:
        # Check cancellation before starting
        if await _is_cancel_requested(run_id, redis_client):
            logger.info(f"[Revalidate {run_id}] Cancellation requested, aborting.")
            raise CancellationRequested(f"Revalidation of run {run_id} was cancelled by user.")

        # Process rows in batches using keyset pagination (WHERE row_index > last_row_index)
        batch_number = 0
        while True:
            logger.info(
                f"[Revalidate {run_id}] Processing batch {batch_number} "
                f"(from row_index > {last_row_index})..."
            )

            # Check cancellation at batch boundary
            if await _is_cancel_requested(run_id, redis_client):
                logger.info(f"[Revalidate {run_id}] Cancellation requested at batch {batch_number}, aborting.")
                raise CancellationRequested(f"Revalidation of run {run_id} was cancelled by user.")

            try:
                async with session_factory() as session:
                    # Load one batch of rows using keyset pagination (WHERE row_index > last).
                    # selectinload avoids cartesian product: issues fetched in separate batched INs.
                    result = await session.execute(
                        select(ReconRow)
                        .where(ReconRow.run_id == UUID(run_id))
                        .where(ReconRow.row_index > last_row_index)
                        .order_by(ReconRow.row_index)
                        .limit(_REVALIDATE_BATCH_SIZE)
                        .options(
                            selectinload(ReconRow.cells).selectinload(ReconCell.issues)
                        )
                    )
                    rows = list(result.unique().scalars().all())
                    if not rows:
                        break

                    logger.info(
                        f"[Revalidate {run_id}] Loaded batch {batch_number} of {len(rows)} rows "
                        f"(row_index {rows[0].row_index}..{rows[-1].row_index})."
                    )

                    # Build raw validation batch from original_value
                    raw_batch: list[dict[str, str | None]] = []
                    for row in rows:
                        row_dict: dict[str, str | None] = {}
                        for cell in row.cells:
                            row_dict[cell.column_name] = cell.original_value
                        raw_batch.append(row_dict)

                    # Re-run validation on this batch
                    logger.info(f"[Revalidate {run_id}] Validating batch {batch_number} ({len(raw_batch)} rows)...")
                    validation = validate_batch(raw_batch)

                    # Diff and update rows/cells/issues
                    batch_errors = 0
                    for row, cell_results in zip(rows, validation):
                        results_by_col = {c.column_name: c for c in cell_results}
                        new_row_error = any(c.is_errored for c in cell_results)

                        # Only update row.has_error if it changed
                        if row.has_error != new_row_error:
                            row.has_error = new_row_error

                        if new_row_error:
                            batch_errors += 1

                        # Diff each cell
                        for cell in row.cells:
                            result = results_by_col.get(cell.column_name)
                            new_is_errored = bool(result and result.is_errored)
                            new_suggested = result.suggested_fix if result else None

                            # Only update if state changed
                            if cell.is_errored != new_is_errored:
                                cell.is_errored = new_is_errored
                            if cell.suggested_fix != new_suggested:
                                cell.suggested_fix = new_suggested

                            # Diff issues: handle multiple issues with same rule_id gracefully
                            # Index all existing issues (rule_id may appear multiple times if malformed)
                            existing_by_rule: dict[str, list[ReconCellIssue]] = {}
                            for issue in cell.issues:
                                if issue.rule_id not in existing_by_rule:
                                    existing_by_rule[issue.rule_id] = []
                                existing_by_rule[issue.rule_id].append(issue)

                            new_issues = result.issues if result else []
                            new_rule_ids = {issue.rule_id for issue in new_issues}

                            # Delete issues that are no longer in results
                            for rule_id, issues in existing_by_rule.items():
                                if rule_id not in new_rule_ids:
                                    for issue in issues:
                                        session.delete(issue)

                            # Add/update issues that are in results
                            for new_issue in new_issues:
                                if new_issue.rule_id in existing_by_rule:
                                    # Assume ≤1 issue per rule_id; update the first (canonical)
                                    existing = existing_by_rule[new_issue.rule_id][0]
                                    if existing.message != new_issue.message:
                                        existing.message = new_issue.message
                                    if existing.suggested_fix != new_issue.suggested_fix:
                                        existing.suggested_fix = new_issue.suggested_fix
                                else:
                                    # New issue — add it
                                    session.add(
                                        ReconCellIssue(
                                            cell_id=cell.id,
                                            rule_id=new_issue.rule_id,
                                            message=new_issue.message,
                                            suggested_fix=new_issue.suggested_fix,
                                        )
                                    )

                    # Commit this batch
                    await session.commit()
                    logger.info(
                        f"[Revalidate {run_id}] Batch {batch_number} complete: {len(rows)} rows, "
                        f"{batch_errors} with errors."
                    )

                    total_rows += len(rows)
                    error_row_count += batch_errors
                    last_row_index = rows[-1].row_index
                    batch_number += 1

            except Exception as batch_exc:  # noqa: BLE001
                # Batch-level error: log and roll back this batch, leave run status at "running"
                # so a retry sees the same incomplete state and can resume
                logger.error(
                    f"[Revalidate {run_id}] Batch {batch_number} failed (rows from row_index > {last_row_index}): {batch_exc}",
                    exc_info=True,
                )
                # Re-raise to let the outer task catch and mark the run as failed
                raise

        # Update run aggregates and status in final transaction
        logger.info(f"[Revalidate {run_id}] All batches complete. Updating run aggregates...")
        async with session_factory() as session:
            run = await session.get(ReconRun, UUID(run_id))
            if run is not None:
                run.row_count = total_rows
                run.error_row_count = error_row_count
                run.status = "validated"
                await session.commit()
            else:
                logger.error(f"[Revalidate {run_id}] ReconRun not found when updating aggregates")

        logger.info(
            f"[Revalidate {run_id}] Revalidation complete: {total_rows} rows, {error_row_count} with errors."
        )

    finally:
        await engine.dispose()

    return total_rows, error_row_count


async def _update_run_status_async(run_id: str, status: str) -> None:
    """Set the run status (used for running/failed transitions).

    Args:
        run_id: The ReconRun UUID string.
        status: New status to set.

    Raises:
        Exception: If database update fails (caller should catch and log).
    """
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
            else:
                logger.error(f"ReconRun {run_id} not found when updating status to {status}")
    except Exception as exc:  # noqa: BLE001
        logger.error(f"Failed to update ReconRun {run_id} status to {status}: {exc}")
        raise
    finally:
        await engine.dispose()


async def _update_job_status_async(
    job_id: str,
    status: str,
    error_message: str | None = None,
) -> None:
    """Update the linked job's status.

    Args:
        job_id: The Job UUID string.
        status: New status to set.
        error_message: Optional error message for failed status.

    Raises:
        Exception: If database update fails (caller should catch and log).
    """
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
    except Exception as exc:  # noqa: BLE001
        logger.error(f"Failed to update Job {job_id} status to {status}: {exc}")
        raise
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

    try:
        asyncio.run(_update_job_status_async(job_id, "running"))
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to update job status to running on startup: %s", exc)

    try:
        asyncio.run(_update_run_status_async(run_id, "running"))
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to update run status to running on startup: %s", exc)

    try:
        # Check cancellation before starting extraction (Issue #3)
        if asyncio.run(_is_cancel_requested(run_id, redis_client)):
            _publish({"type": "log", "data": "Cancellation requested before extraction started."})
            _publish({"type": "status", "data": "cancelled"})
            try:
                asyncio.run(_update_run_status_async(run_id, "cancelled"))
                asyncio.run(_update_job_status_async(job_id, "cancelled"))
            except Exception as exc:  # noqa: BLE001
                logger.error("Failed to update status to cancelled: %s", exc)
            return {"status": "cancelled"}

        # Import here so the API process can run without pyodbc installed.
        from api.services.daily_recon_source import extract_rows

        _publish({"type": "log", "data": "Connecting to SQL Server source..."})
        rows = extract_rows(query)
        _publish({"type": "log", "data": f"Extracted {len(rows)} rows."})
        _publish({"type": "progress", "data": 50})

        # Check cancellation after extraction (Issue #3)
        if asyncio.run(_is_cancel_requested(run_id, redis_client)):
            _publish({"type": "log", "data": "Cancellation requested after extraction."})
            _publish({"type": "status", "data": "cancelled"})
            try:
                asyncio.run(_update_run_status_async(run_id, "cancelled"))
                asyncio.run(_update_job_status_async(job_id, "cancelled"))
            except Exception as exc:  # noqa: BLE001
                logger.error("Failed to update status to cancelled: %s", exc)
            return {"status": "cancelled"}

        total, errors = asyncio.run(_persist_async(run_id, rows))
        _publish(
            {
                "type": "log",
                "data": f"Persisted {total} rows ({errors} with errors).",
            }
        )
        _publish({"type": "progress", "data": 100})
        _publish({"type": "status", "data": "success"})

        try:
            asyncio.run(_update_job_status_async(job_id, "success"))
        except Exception as exc:  # noqa: BLE001
            logger.error("Failed to update job status to success: %s", exc)

        return {"status": "success", "rowCount": total, "errorRowCount": errors}

    except Exception as exc:  # noqa: BLE001
        error_msg = f"Daily reconciliation failed: {exc}"
        logger.exception(error_msg)
        _publish({"type": "log", "data": error_msg})
        _publish({"type": "status", "data": "failed"})
        _publish({"type": "progress", "data": 100})

        try:
            asyncio.run(_update_run_status_async(run_id, "failed"))
        except Exception as update_exc:  # noqa: BLE001
            logger.error("Failed to update run status to failed: %s", update_exc)

        try:
            asyncio.run(_update_job_status_async(job_id, "failed", error_message=error_msg))
        except Exception as update_exc:  # noqa: BLE001
            logger.error("Failed to update job status to failed: %s", update_exc)

        return {"status": "failed", "error": str(exc)}


@celery_app.task(bind=True, name="api.tasks.daily_recon_tasks.revalidate_run")
def revalidate_run(
    self: Task,
    job_id: str,
    run_id: str,
) -> dict[str, object]:
    """Re-validate an existing run (no SQL extraction).

    Args:
        job_id: UUID string of the parent job.
        run_id: UUID string of the ReconRun row.

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
    _publish({"type": "progress", "data": 10})
    _publish({"type": "log", "data": f"Starting re-validation of run {run_id}..."})
    asyncio.run(_update_job_status_async(job_id, "running"))
    asyncio.run(_update_run_status_async(run_id, "running"))

    try:
        _publish({"type": "log", "data": "Re-running validation on stored rows..."})
        logger.info(f"Revalidate task started for run {run_id}, job {job_id}")
        total, errors = asyncio.run(_revalidate_async(run_id, redis_client))
        _publish(
            {
                "type": "log",
                "data": f"✓ Re-validation complete: {total} rows, {errors} with errors.",
            }
        )
        _publish({"type": "progress", "data": 100})
        _publish({"type": "status", "data": "success"})
        asyncio.run(_update_job_status_async(job_id, "success"))
        logger.info(f"Revalidate task succeeded for run {run_id}: {total} rows, {errors} errors")

        return {"status": "success", "rowCount": total, "errorRowCount": errors}

    except CancellationRequested as exc:
        # User requested cancellation
        error_msg = str(exc)
        logger.info(f"Revalidate task cancelled for run {run_id}: {error_msg}")
        _publish({"type": "log", "data": "✓ Revalidation cancelled by user."})
        _publish({"type": "status", "data": "cancelled"})
        _publish({"type": "progress", "data": 100})
        asyncio.run(_update_run_status_async(run_id, "cancelled"))
        asyncio.run(_update_job_status_async(job_id, "cancelled"))

        # Clean up the cancellation flag from Redis
        settings = get_settings()
        redis_client = redis_lib.from_url(settings.redis_url)
        try:
            redis_client.delete(f"revalidate:{run_id}:cancel")
        except Exception as e:  # noqa: BLE001
            logger.warning(f"Failed to delete cancellation flag: {e}")

        return {"status": "cancelled", "error": error_msg}

    except Exception as exc:  # noqa: BLE001
        error_msg = f"Re-validation failed: {exc}"
        logger.exception(error_msg)
        _publish({"type": "log", "data": error_msg})
        _publish({"type": "status", "data": "failed"})
        _publish({"type": "progress", "data": 100})
        asyncio.run(_update_run_status_async(run_id, "failed"))
        asyncio.run(_update_job_status_async(job_id, "failed", error_message=error_msg))
        logger.error(f"Revalidate task failed for run {run_id}: {error_msg}")
        return {"status": "failed", "error": str(exc)}

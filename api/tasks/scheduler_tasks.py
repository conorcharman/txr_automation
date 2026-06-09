"""
Scheduler Tasks
===============

Celery periodic task that polls the database for schedules that are due and
dispatches a ``run_script`` task for each one.

The ``check_and_run_schedules`` task is registered in the Celery beat schedule
to run every minute.  It:

1. Queries the ``schedules`` table for rows where ``is_active = True`` and
   ``next_run_at <= now()``.
2. For each due schedule, creates a ``jobs`` row and dispatches
   ``run_script.delay()``.
3. Advances ``last_run_at`` and recalculates ``next_run_at`` via
   ``schedule_service.mark_triggered()``.

This mirrors the ``_RunnerThread`` polling logic from the desktop
``src/gui/scheduler/engine.py``, replacing Qt timers with Celery beat.

Usage::

    # Celery beat runs this automatically every 60 seconds.
    # To trigger manually during development:
    celery -A api.tasks.celery_app call api.tasks.scheduler_tasks.check_and_run_schedules
"""

import asyncio
import logging
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from api.config import get_settings
from api.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


async def _run_due_schedules() -> int:
    """Open a DB session, find due schedules, and dispatch their jobs.

    This coroutine is called via ``asyncio.run()`` from the synchronous
    Celery task context.

    Returns:
        The number of schedules that were triggered.
    """
    from api.routers.jobs import SCRIPT_MODULES
    from api.services.job_service import job_service
    from api.services.schedule_service import schedule_service
    from api.tasks.script_tasks import run_script

    settings = get_settings()
    engine = create_async_engine(settings.database_url, echo=False)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    triggered = 0
    try:
        async with session_factory() as db:
            due = await schedule_service.get_due_schedules(db)
            for schedule in due:
                module_path = SCRIPT_MODULES.get(schedule.script_name)
                if module_path is None:
                    logger.warning(
                        "Skipping schedule '%s': script '%s' is not registered.",
                        schedule.name,
                        schedule.script_name,
                    )
                    continue

                config = schedule.config_data or {}
                try:
                    job = await job_service.create_job(db, schedule.script_name, config)
                    run_script.delay(str(job.id), module_path, [], config)
                    await schedule_service.mark_triggered(
                        db, schedule, status="pending"
                    )
                    triggered += 1
                    logger.info(
                        "Triggered schedule '%s' — job %s dispatched.",
                        schedule.name,
                        job.id,
                    )
                except Exception:  # noqa: BLE001
                    logger.exception("Failed to trigger schedule '%s'.", schedule.name)
    finally:
        await engine.dispose()

    return triggered


@celery_app.task(name="api.tasks.scheduler_tasks.check_and_run_schedules")
def check_and_run_schedules() -> dict:
    """Poll the database for due schedules and dispatch their jobs.

    This task is intended to be run every minute via Celery beat.  It creates
    a fresh async engine and session for each invocation because Celery workers
    do not run a persistent event loop.

    Returns:
        A dict with key ``"triggered"`` containing the count of dispatched jobs.
    """
    try:
        triggered = asyncio.run(_run_due_schedules())
        logger.info("check_and_run_schedules: triggered %d schedule(s).", triggered)
        return {"triggered": triggered}
    except Exception:  # noqa: BLE001
        logger.exception("check_and_run_schedules encountered an unexpected error.")
        return {"triggered": 0}


# ---------------------------------------------------------------------------
# Pipeline beat task
# ---------------------------------------------------------------------------


async def _run_due_pipelines() -> int:
    """Open a DB session, find due pipelines, and dispatch their jobs.

    This coroutine is called via ``asyncio.run()`` from the synchronous
    Celery task context.

    Returns:
        The number of pipelines that were triggered.
    """
    from api.services.job_service import job_service
    from api.services.pipeline_service import pipeline_service
    from api.tasks.pipeline_tasks import run_pipeline

    settings = get_settings()
    engine = create_async_engine(settings.database_url, echo=False)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    triggered = 0
    try:
        async with session_factory() as db:
            due = await pipeline_service.get_due_pipelines(db)
            for pipeline in due:
                # For quarterly pipelines, auto-calculate the fiscal period.
                fiscal_year = pipeline.fiscal_year
                quarter = pipeline.quarter
                if pipeline.frequency == "quarterly":
                    from api.utils.fiscal_date import get_completed_quarter

                    fiscal_year, quarter = get_completed_quarter(
                        datetime.now(tz=timezone.utc)
                    )
                    pipeline.fiscal_year = fiscal_year
                    pipeline.quarter = quarter

                config_snapshot = {
                    "pipeline_id": str(pipeline.id),
                    "pipeline_name": pipeline.name,
                    "fiscal_year": fiscal_year,
                    "quarter": quarter,
                    "selected_scripts": pipeline.selected_scripts,
                    "config_overrides": pipeline.config_overrides,
                    "stop_on_error": pipeline.stop_on_error,
                }
                try:
                    job = await job_service.create_job(
                        db, f"pipeline:{pipeline.name}", config_snapshot
                    )
                    run_pipeline.delay(str(job.id), config_snapshot)
                    await pipeline_service.mark_triggered(
                        db, pipeline, status="pending"
                    )
                    triggered += 1
                    logger.info(
                        "Triggered pipeline '%s' — job %s dispatched.",
                        pipeline.name,
                        job.id,
                    )
                except Exception:  # noqa: BLE001
                    logger.exception("Failed to trigger pipeline '%s'.", pipeline.name)
    finally:
        await engine.dispose()

    return triggered


@celery_app.task(name="api.tasks.scheduler_tasks.check_and_run_pipelines")
def check_and_run_pipelines() -> dict:
    """Poll the database for due pipelines and dispatch their jobs.

    This task is intended to be run every minute via Celery beat.

    Returns:
        A dict with key ``"triggered"`` containing the count of dispatched jobs.
    """
    try:
        triggered = asyncio.run(_run_due_pipelines())
        logger.info("check_and_run_pipelines: triggered %d pipeline(s).", triggered)
        return {"triggered": triggered}
    except Exception:  # noqa: BLE001
        logger.exception("check_and_run_pipelines encountered an unexpected error.")
        return {"triggered": 0}


# ---------------------------------------------------------------------------
# Reconciliation beat task
# ---------------------------------------------------------------------------


async def _run_due_reconciliations() -> int:
    """Open a DB session, find due reconciliations, and dispatch their jobs.

    Returns:
        The number of reconciliations that were triggered.
    """
    from api.services.job_service import job_service
    from api.services.reconciliation_service import reconciliation_service
    from api.tasks.reconciliation_tasks import run_reconciliation

    settings = get_settings()
    engine = create_async_engine(settings.database_url, echo=False)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    triggered = 0
    try:
        async with session_factory() as db:
            due = await reconciliation_service.get_due_reconciliations(db)
            for rec in due:
                config_snapshot = {
                    "reconciliation_id": str(rec.id),
                    "reconciliation_name": rec.name,
                    "rec_period_days": rec.rec_period_days,
                    "lookback_days": rec.lookback_days,
                    "selected_scripts": rec.selected_scripts,
                    "config_overrides": rec.config_overrides,
                    "stop_on_error": rec.stop_on_error,
                }
                try:
                    job = await job_service.create_job(
                        db, f"reconciliation:{rec.name}", config_snapshot
                    )
                    run_reconciliation.delay(str(job.id), config_snapshot)
                    await reconciliation_service.mark_triggered(
                        db, rec, status="pending"
                    )
                    triggered += 1
                    logger.info(
                        "Triggered reconciliation '%s' — job %s dispatched.",
                        rec.name,
                        job.id,
                    )
                except Exception:  # noqa: BLE001
                    logger.exception("Failed to trigger reconciliation '%s'.", rec.name)
    finally:
        await engine.dispose()

    return triggered


@celery_app.task(name="api.tasks.scheduler_tasks.check_and_run_reconciliations")
def check_and_run_reconciliations() -> dict:
    """Poll the database for due reconciliations and dispatch their jobs.

    This task is intended to be run every minute via Celery beat.

    Returns:
        A dict with key ``"triggered"`` containing the count of dispatched jobs.
    """
    try:
        triggered = asyncio.run(_run_due_reconciliations())
        logger.info(
            "check_and_run_reconciliations: triggered %d reconciliation(s).",
            triggered,
        )
        return {"triggered": triggered}
    except Exception:  # noqa: BLE001
        logger.exception(
            "check_and_run_reconciliations encountered an unexpected error."
        )
        return {"triggered": 0}

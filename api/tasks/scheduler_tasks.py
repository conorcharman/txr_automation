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
                    job = await job_service.create_job(
                        db, schedule.script_name, config
                    )
                    run_script.delay(str(job.id), module_path, [], config)
                    await schedule_service.mark_triggered(db, schedule, status="pending")
                    triggered += 1
                    logger.info(
                        "Triggered schedule '%s' — job %s dispatched.",
                        schedule.name,
                        job.id,
                    )
                except Exception:  # noqa: BLE001
                    logger.exception(
                        "Failed to trigger schedule '%s'.", schedule.name
                    )
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

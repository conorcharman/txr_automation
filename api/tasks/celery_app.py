"""
Celery Application
==================

Initialises the shared Celery application instance used by all task
modules in ``api/tasks/``.

Pattern for Phase 2+ tasks
---------------------------
Every long-running task must follow this pattern:

    1. Accept ``job_id: str`` as its first argument.
    2. Update the ``jobs`` table: PENDING → RUNNING on start.
    3. Capture script stdout via ``contextlib.redirect_stdout`` + ``io.StringIO``.
    4. Call the script: ``module.main(argv)`` — same pattern as
       ``src/gui/workers/script_runner.py``.
    5. Publish each log line to Redis:
       ``redis.publish(f"job:{job_id}:logs", json.dumps({"type": "log", "data": line}))``.
    6. Update the ``jobs`` table: RUNNING → SUCCESS | FAILED on completion.

Usage:
    from api.tasks.celery_app import celery_app

    @celery_app.task
    def my_task(job_id: str, ...) -> None:
        ...
"""

import asyncio
import logging
from datetime import datetime, timezone

from celery import Celery
from celery.signals import worker_ready

from api.config import get_settings

_log = logging.getLogger(__name__)

_settings = get_settings()

celery_app = Celery(
    "txr_automation",
    broker=_settings.redis_url,
    backend=_settings.redis_url,
)


@worker_ready.connect
def _cleanup_orphaned_jobs(sender, **kwargs) -> None:  # noqa: ANN001
    """Mark any 'running' jobs as 'failed' when the worker (re)starts.

    If a previous worker process was killed (OOM or SIGKILL), any jobs that
    were in-progress will be permanently stuck in 'running' state in the
    database. This signal handler resets them to 'failed' on startup so the
    UI does not show permanently stalled jobs.
    """

    async def _reset() -> None:
        from sqlalchemy import update
        from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

        from api.models.job import Job

        engine = create_async_engine(_settings.database_url, echo=False)
        factory = async_sessionmaker(engine, expire_on_commit=False)
        try:
            async with factory() as session:
                result = await session.execute(
                    update(Job)
                    .where(Job.status == "running")
                    .values(
                        status="failed",
                        error_message="Worker was restarted while job was in progress.",
                        completed_at=datetime.now(tz=timezone.utc),
                    )
                )
                await session.commit()
                if result.rowcount:
                    _log.warning(
                        "Marked %d orphaned running job(s) as failed on worker startup.",
                        result.rowcount,
                    )
        except Exception as exc:  # noqa: BLE001
            _log.error("Failed to clean up orphaned jobs on startup: %s", exc)
        finally:
            await engine.dispose()

    asyncio.run(_reset())


celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    # Explicitly include task modules so the worker registers them on startup.
    include=[
        "api.tasks.script_tasks",
        "api.tasks.scheduler_tasks",
        "api.tasks.pipeline_tasks",
        "api.tasks.reconciliation_tasks",
    ],
    # Celery beat periodic tasks.
    beat_schedule={
        "check-and-run-schedules-every-minute": {
            "task": "api.tasks.scheduler_tasks.check_and_run_schedules",
            "schedule": 60.0,  # seconds
        },
        "check-and-run-pipelines-every-minute": {
            "task": "api.tasks.scheduler_tasks.check_and_run_pipelines",
            "schedule": 60.0,  # seconds
        },
        "check-and-run-reconciliations-every-minute": {
            "task": "api.tasks.scheduler_tasks.check_and_run_reconciliations",
            "schedule": 60.0,  # seconds
        },
    },
)

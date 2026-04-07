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

from celery import Celery

from api.config import get_settings

_settings = get_settings()

celery_app = Celery(
    "txr_automation",
    broker=_settings.redis_url,
    backend=_settings.redis_url,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    # Explicitly include task modules so the worker registers them on startup.
    include=["api.tasks.script_tasks"],
)

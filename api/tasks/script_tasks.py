"""
Script Tasks
============

Generic Celery task that imports and runs any registered script module,
capturing stdout/stderr and publishing log lines to a Redis pub/sub
channel for real-time streaming to the frontend WebSocket clients.

The DB-update helper uses ``asyncio.run()`` to call the async
``JobService`` from within the synchronous Celery worker context, since
Celery workers do not have a running event loop.

Pattern:
    The task mirrors the Qt-based ``ScriptRunnerWorker`` in
    ``src/gui/workers/script_runner.py``, replacing Qt signals with
    Redis pub/sub messages:

    Redis channel: ``job:{job_id}:logs``
    Message shapes:
        - ``{"type": "status", "data": "running" | "success" | "failed"}``
        - ``{"type": "log", "data": "<line>"}``

Usage:
    from api.tasks.script_tasks import run_script

    run_script.delay(
        job_id="<uuid>",
        module_path="src.accuracy_testing.scripts.buyer_id_validation",
        argv=["--config", "/path/to/config.yaml"],
        config_snapshot={"fiscalYear": "FY26"},
    )
"""

import asyncio
import contextlib
import importlib
import io
import json
import logging
import os
import sys
import threading
from typing import Any

import redis as redis_lib
from celery import Task

from api.config import get_settings
from api.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)

# Lock protecting global sys.argv mutations across concurrent Celery tasks.
_argv_lock = threading.Lock()


# ---------------------------------------------------------------------------
# Async DB-update helper (called via asyncio.run from the Celery worker)
# ---------------------------------------------------------------------------


async def _update_status_async(
    job_id: str,
    status: str,
    error_message: str | None = None,
    output_files: list[str] | None = None,
) -> None:
    """Open a fresh async DB session and update the job status.

    A new ``AsyncEngine`` is created and disposed on each call because
    ``asyncio.run()`` starts a fresh event loop every time, and asyncpg
    connections are bound to the loop that created them.  This is
    acceptable because status updates happen only twice per task
    (running + final).

    Args:
        job_id: String UUID of the job to update.
        status: New status string.
        error_message: Optional error description to store.
        output_files: Optional list of output file paths to record.
    """
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from api.services.job_service import job_service

    settings = get_settings()
    engine = create_async_engine(settings.database_url, echo=False)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    try:
        async with session_factory() as session:
            await job_service.update_status(
                session,
                job_id,
                status,
                error_message=error_message,
                output_files=output_files,
            )
    finally:
        await engine.dispose()


def _sync_update_status(
    job_id: str,
    status: str,
    error_message: str | None = None,
    output_files: list[str] | None = None,
) -> None:
    """Synchronous wrapper that calls ``_update_status_async`` via asyncio.run.

    Args:
        job_id: String UUID of the job to update.
        status: New status string.
        error_message: Optional error description to store.
        output_files: Optional list of output file paths to record.
    """
    asyncio.run(
        _update_status_async(
            job_id,
            status,
            error_message=error_message,
            output_files=output_files,
        )
    )


# ---------------------------------------------------------------------------
# Celery task
# ---------------------------------------------------------------------------


@celery_app.task(bind=True, name="api.tasks.script_tasks.run_script")
def run_script(
    self: Task,
    job_id: str,
    module_path: str,
    argv: list[str],
    config_snapshot: dict,
) -> dict[str, Any]:
    """Import and run a script module, streaming output to Redis pub/sub.

    The task follows this lifecycle:

    1. Connect to Redis.
    2. Mark the job as ``running`` in the database and publish a status message.
    3. Import ``module_path`` and redirect sys.stdout/sys.stderr to a buffer.
    4. Call ``module.main(argv)``, publishing each non-empty output line to Redis.
    5. On success: publish ``success`` status, update DB, and return a result dict.
    6. On exception: publish ``failed`` status, update DB with the error, re-raise.

    Args:
        job_id: UUID string of the associated job row in the database.
        module_path: Dotted Python module path, e.g.
            ``"src.accuracy_testing.scripts.buyer_id_validation"``.
        argv: List of CLI arguments to pass to ``module.main()``.
        config_snapshot: Configuration dict stored for audit purposes (not used
            directly by the task).

    Returns:
        A dict with keys ``"status"`` and ``"output_files"`` on success.

    Raises:
        Exception: Re-raises any exception from ``module.main()`` after
            publishing the failure status to Redis and updating the database.
    """
    settings = get_settings()
    redis_client = redis_lib.from_url(settings.redis_url)
    channel = f"job:{job_id}:logs"

    def _publish(message: dict) -> None:
        """Publish a JSON message to the job's Redis log channel."""
        try:
            redis_client.publish(channel, json.dumps(message))
        except Exception as exc:  # noqa: BLE001
            logger.warning("Redis publish failed for job %s: %s", job_id, exc)

    # ── Mark running ────────────────────────────────────────────────────────
    _sync_update_status(job_id, "running")
    _publish({"type": "status", "data": "running"})

    # ── Import and run the module ────────────────────────────────────────────
    output_buffer = io.StringIO()
    old_stdout = sys.stdout
    old_stderr = sys.stderr

    # Identify temp config files created by ScriptRunnerService so we can
    # clean them up after the script finishes.
    _temp_files: list[str] = [
        arg for arg in argv
        if arg.endswith(".yaml") and os.sep + "tmp" in arg.lower()
    ]

    try:
        module = importlib.import_module(module_path)

        with contextlib.redirect_stdout(output_buffer), contextlib.redirect_stderr(
            output_buffer
        ):
            # Protect sys.argv from concurrent task corruption.
            with _argv_lock:
                old_argv = sys.argv
                sys.argv = [module_path] + argv
            try:
                module.main()
            except SystemExit as exc:
                # Treat non-zero SystemExit as a failure.
                exit_code = exc.code if isinstance(exc.code, int) else 1
                if exit_code != 0:
                    raise RuntimeError(
                        f"Script exited with code {exit_code}"
                    ) from exc
            finally:
                with _argv_lock:
                    sys.argv = old_argv

        # Publish captured output line by line.
        output = output_buffer.getvalue()
        for line in output.splitlines():
            if line.strip():
                _publish({"type": "log", "data": line})

        # ── Success ─────────────────────────────────────────────────────────
        _sync_update_status(job_id, "success", output_files=[])
        _publish({"type": "status", "data": "success"})
        return {"status": "success", "output_files": []}

    except Exception as exc:
        # Ensure stdout is always restored on unexpected error.
        sys.stdout = old_stdout
        sys.stderr = old_stderr

        # Flush any partial output.
        partial_output = output_buffer.getvalue()
        for line in partial_output.splitlines():
            if line.strip():
                _publish({"type": "log", "data": line})

        error_str = f"{type(exc).__name__}: {exc}"
        _publish({"type": "log", "data": error_str})
        _publish({"type": "status", "data": "failed"})
        _sync_update_status(job_id, "failed", error_message=error_str)
        raise

    finally:
        sys.stdout = old_stdout
        sys.stderr = old_stderr
        # Clean up temporary config YAML files written by ScriptRunnerService.
        for tmp in _temp_files:
            try:
                os.unlink(tmp)
            except OSError:
                pass
        try:
            redis_client.close()
        except Exception:  # noqa: BLE001
            pass

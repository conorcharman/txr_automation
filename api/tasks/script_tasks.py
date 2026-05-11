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
    log_output: str | None = None,
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
        log_output: Optional full captured stdout/stderr to persist.
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
                log_output=log_output,
            )
    finally:
        await engine.dispose()


def _sync_update_status(
    job_id: str,
    status: str,
    error_message: str | None = None,
    output_files: list[str] | None = None,
    log_output: str | None = None,
) -> None:
    """Synchronous wrapper that calls ``_update_status_async`` via asyncio.run.

    Args:
        job_id: String UUID of the job to update.
        status: New status string.
        error_message: Optional error description to store.
        output_files: Optional list of output file paths to record.
        log_output: Optional full captured stdout/stderr to persist.
    """
    asyncio.run(
        _update_status_async(
            job_id,
            status,
            error_message=error_message,
            output_files=output_files,
            log_output=log_output,
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

    # Some scripts use non-zero exit codes for informational results rather
    # than errors.  Map module paths to the set of codes that should be
    # treated as successful completion.
    _ACCEPTED_EXIT_CODES: dict[str, set[int]] = {
        # check_reportability exits with 2 when the instrument is NOT reportable.
        "src.firds.scripts.check_reportability": {2},
    }
    accepted_exit_codes = _ACCEPTED_EXIT_CODES.get(module_path, set())

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
        with contextlib.redirect_stdout(output_buffer), contextlib.redirect_stderr(
            output_buffer
        ):
            # Evict any cached version and re-import *inside* the redirect so
            # that module-level logging handlers (e.g. StructuredLogger's
            # StreamHandler, which stores sys.stderr at init time) pick up the
            # capture buffer rather than the worker's original stderr.
            sys.modules.pop(module_path, None)
            module = importlib.import_module(module_path)

            # Protect sys.argv from concurrent task corruption.
            with _argv_lock:
                old_argv = sys.argv
                sys.argv = [module_path] + argv
            try:
                module.main()
            except SystemExit as exc:
                # Treat non-zero SystemExit as a failure *unless* the exit
                # code is an expected "informational" code for this script.
                # FIRDS check_reportability uses exit-code 2 to signal
                # "not reportable" — that is a valid result, not an error.
                exit_code = exc.code if isinstance(exc.code, int) else 1
                if exit_code != 0 and exit_code not in accepted_exit_codes:
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
        _sync_update_status(job_id, "success", output_files=[], log_output=output)
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
        full_log = partial_output + ("\n" if partial_output else "") + error_str
        _sync_update_status(job_id, "failed", error_message=error_str, log_output=full_log)
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


# ---------------------------------------------------------------------------
# Incidents Celery task
# ---------------------------------------------------------------------------


@celery_app.task(bind=True, name="api.tasks.script_tasks.run_incidents")
def run_incidents(
    self: Task,
    job_id: str,
    incident_configs: list[dict[str, Any]],
    stop_on_error: bool = False,
) -> dict[str, Any]:
    """Run multiple incidents sequentially, each in single mode.

    Each entry in ``incident_configs`` is a dict with keys
    ``module_path``, ``argv``, and ``config_snapshot``.  The task imports
    the module and calls ``module.main()`` for each incident, streaming
    logs to Redis and respecting ``stop_on_error``.

    Args:
        job_id: UUID string of the parent job.
        incident_configs: List of per-incident dicts with ``module_path``,
            ``argv``, and ``config_snapshot`` keys.
        stop_on_error: If ``True``, abort on first failure.

    Returns:
        A dict with ``"status"`` and ``"results"`` keys.
    """
    settings = get_settings()
    redis_client = redis_lib.from_url(settings.redis_url)
    channel = f"job:{job_id}:logs"

    def _publish(message: dict) -> None:
        try:
            redis_client.publish(channel, json.dumps(message))
        except Exception as exc:  # noqa: BLE001
            logger.warning("Redis publish failed for job %s: %s", job_id, exc)

    _sync_update_status(job_id, "running")
    _publish({"type": "status", "data": "running"})

    full_output = io.StringIO()
    results: list[dict] = []
    failed = False
    total = len(incident_configs)
    temp_files: list[str] = []

    for idx, ic in enumerate(incident_configs, 1):
        module_path = ic["module_path"]
        argv: list[str] = ic["argv"]
        snapshot = ic.get("config_snapshot", {})
        incident_code = snapshot.get("single", {}).get("incident_code", "unknown")

        # Track temp files for cleanup.
        temp_files.extend(
            arg for arg in argv
            if arg.endswith(".yaml") and os.sep + "tmp" in arg.lower()
        )

        header = f"[{idx}/{total}] Running {incident_code}..."
        _publish({"type": "log", "data": header})
        full_output.write(header + "\n")

        try:
            script_buffer = io.StringIO()

            with _argv_lock:
                old_argv = sys.argv
                sys.argv = [module_path] + argv
            try:
                with contextlib.redirect_stdout(script_buffer), \
                     contextlib.redirect_stderr(script_buffer):
                    # Import inside the redirect so module-level logging
                    # handlers (StructuredLogger's StreamHandler) capture to
                    # script_buffer rather than the worker's original stderr.
                    sys.modules.pop(module_path, None)
                    module = importlib.import_module(module_path)
                    module.main()
            except SystemExit as exc:
                exit_code = exc.code if isinstance(exc.code, int) else 1
                if exit_code != 0:
                    raise RuntimeError(
                        f"Script exited with code {exit_code}"
                    ) from exc
            finally:
                with _argv_lock:
                    sys.argv = old_argv

            output_text = script_buffer.getvalue()
            for line in output_text.splitlines():
                if line.strip():
                    _publish({"type": "log", "data": line})
            full_output.write(output_text)

            results.append({"incident": incident_code, "status": "success"})
            done_msg = f"  ✓ {incident_code} completed."
            _publish({"type": "log", "data": done_msg})
            full_output.write(done_msg + "\n")

        except Exception as exc:  # noqa: BLE001
            error_msg = f"  ✗ {incident_code} failed: {exc}"
            _publish({"type": "log", "data": error_msg})
            full_output.write(error_msg + "\n")
            results.append({
                "incident": incident_code,
                "status": "failed",
                "error": str(exc),
            })
            failed = True
            if stop_on_error:
                break

    final_status = "failed" if failed else "success"
    _publish({"type": "status", "data": final_status})
    _sync_update_status(
        job_id,
        final_status,
        error_message="Incident run completed with failures." if failed else None,
        log_output=full_output.getvalue(),
    )

    # Clean up temp YAML files.
    for tmp in temp_files:
        try:
            os.unlink(tmp)
        except OSError:
            pass
    try:
        redis_client.close()
    except Exception:  # noqa: BLE001
        pass

    return {"status": final_status, "results": results}

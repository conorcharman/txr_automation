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
import re
import sys
import threading
from pathlib import Path
from typing import Any, Callable

import redis as redis_lib
from celery import Task

from api.config import get_settings
from api.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)

_TEMPLATE_CODE_RE = re.compile(
    r"^(?:FY\d{2}\s+Q[1-4]\s+)?(?P<code>\d+_\d+)\.csv$",
    re.IGNORECASE,
)

# Lock protecting global sys.argv mutations across concurrent Celery tasks.
_argv_lock = threading.Lock()


class _ProgressEstimator:
    """Estimate percentage completion from task lifecycle and known log patterns."""

    def __init__(self, module_path: str) -> None:
        self._module_path = module_path
        self._last_percent = 0
        self._fulins_total: int | None = None
        self._fulcan_total: int | None = None
        self._heartbeat_count = 0

    @staticmethod
    def _clamp(percent: int) -> int:
        return max(0, min(100, percent))

    def _set(self, percent: int) -> int | None:
        bounded = self._clamp(percent)
        if bounded <= self._last_percent:
            return None
        self._last_percent = bounded
        return bounded

    def on_running(self) -> int | None:
        """Emit an initial non-zero progress once the job starts."""
        return self._set(5)

    def on_log_line(self, line: str) -> int | None:
        """Infer progress from known script output patterns."""
        text = line.strip()
        if not text:
            return None

        # FIRDS refresh provides reliable totals and per-file [x/y] markers.
        if self._module_path == "src.firds.scripts.refresh_cache":
            fulins_match = re.search(
                r"Found\s+(\d+)\s+in-scope\s+FULINS\s+file\(s\)\s+to\s+process",
                text,
            )
            if fulins_match:
                self._fulins_total = int(fulins_match.group(1))
                return self._set(10)

            fulcan_match = re.search(
                r"Found\s+(\d+)\s+FULCAN\s+cancellation\s+file\(s\)\s+to\s+process",
                text,
            )
            if fulcan_match:
                self._fulcan_total = int(fulcan_match.group(1))
                return self._set(75)

            bracket = re.search(r"\[(\d+)/(\d+)\]", text)
            if bracket:
                idx = int(bracket.group(1))
                total = max(int(bracket.group(2)), 1)

                if "FULINS" in text:
                    span = 60 if (self._fulcan_total or 0) > 0 else 80
                    return self._set(10 + int((idx / total) * span))

                if "FULCAN" in text:
                    base = 75 if (self._fulins_total or 0) > 0 else 10
                    span = 20 if (self._fulins_total or 0) > 0 else 80
                    return self._set(base + int((idx / total) * span))

            if "FIRDS full refresh complete" in text:
                return self._set(98)

        # Generic fallback: support scripts that log [x/y] progress markers.
        generic = re.search(r"\[(\d+)/(\d+)\]", text)
        if generic:
            idx = int(generic.group(1))
            total = max(int(generic.group(2)), 1)
            return self._set(10 + int((idx / total) * 80))

        return None

    def on_terminal(self) -> int | None:
        """Emit completion progress for terminal states."""
        return self._set(100)


def _publish_progress(
    publish: Callable[[dict], None],
    percent: int | None,
) -> None:
    """Publish progress updates when a higher percentage is available."""
    if percent is None:
        return
    publish({"type": "progress", "data": percent})


class _LiveOutputCapture(io.TextIOBase):
    """Capture stdout/stderr and publish complete lines in real time.

    This file-like object is used with ``contextlib.redirect_stdout`` and
    ``contextlib.redirect_stderr``. It keeps a full in-memory copy of output
    for DB persistence whilst publishing each completed line to Redis as soon
    as it is emitted.
    """

    def __init__(self, publish_line: Callable[[str], None]) -> None:
        self._publish_line = publish_line
        self._buffer = io.StringIO()
        self._partial = ""

    def write(self, s: str) -> int:
        if not s:
            return 0

        self._buffer.write(s)
        chunk = self._partial + s
        lines = chunk.splitlines(keepends=True)

        self._partial = ""
        for line in lines:
            if line.endswith("\n") or line.endswith("\r"):
                text = line.rstrip("\r\n")
                if text.strip():
                    self._publish_line(text)
            else:
                self._partial = line

        return len(s)

    def flush(self) -> None:
        if self._partial.strip():
            self._publish_line(self._partial)
        self._partial = ""

    def getvalue(self) -> str:
        return self._buffer.getvalue()


def _extract_template_incident_code(filename: str) -> str | None:
    """Extract an incident code from a generated template CSV filename."""
    match = _TEMPLATE_CODE_RE.match(filename)
    if match is None:
        return None
    return match.group("code")


def _filter_template_outputs(
    output_directory: str,
    allowed_incident_codes: set[str],
) -> tuple[int, int]:
    """Delete generated template CSVs whose incident codes are not selected.

    Args:
        output_directory: Directory containing generated template CSV files.
        allowed_incident_codes: Selected incident codes to retain.

    Returns:
        Tuple of ``(removed_count, scanned_count)`` where ``scanned_count``
        includes only CSV files matching the template filename pattern.
    """
    base = Path(output_directory)
    if not base.exists() or not base.is_dir():
        return 0, 0

    removed = 0
    scanned = 0
    for csv_path in base.glob("*.csv"):
        code = _extract_template_incident_code(csv_path.name)
        if code is None:
            continue
        scanned += 1
        if code not in allowed_incident_codes:
            csv_path.unlink(missing_ok=True)
            removed += 1
    return removed, scanned


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
    estimator = _ProgressEstimator(module_path)

    def _publish(message: dict) -> None:
        """Publish a JSON message to the job's Redis log channel."""
        try:
            redis_client.publish(channel, json.dumps(message))
        except Exception as exc:  # noqa: BLE001
            logger.warning("Redis publish failed for job %s: %s", job_id, exc)

    # ── Mark running ────────────────────────────────────────────────────────
    _sync_update_status(job_id, "running")
    _publish({"type": "status", "data": "running"})
    _publish_progress(_publish, estimator.on_running())

    def _publish_log_line(line: str) -> None:
        _publish({"type": "log", "data": line})
        _publish_progress(_publish, estimator.on_log_line(line))

    # Some scripts use non-zero exit codes for informational results rather
    # than errors.  Map module paths to the set of codes that should be
    # treated as successful completion.
    _ACCEPTED_EXIT_CODES: dict[str, set[int]] = {
        # check_reportability exits with 2 when the instrument is NOT reportable.
        "src.firds.scripts.check_reportability": {2},
    }
    accepted_exit_codes = _ACCEPTED_EXIT_CODES.get(module_path, set())

    # ── Import and run the module ────────────────────────────────────────────
    output_capture = _LiveOutputCapture(_publish_log_line)
    old_stdout = sys.stdout
    old_stderr = sys.stderr

    # Identify temp config files created by ScriptRunnerService so we can
    # clean them up after the script finishes.
    _temp_files: list[str] = [
        arg for arg in argv
        if arg.endswith(".yaml") and os.sep + "tmp" in arg.lower()
    ]

    try:
        with contextlib.redirect_stdout(output_capture), contextlib.redirect_stderr(
            output_capture
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

        output_capture.flush()
        output = output_capture.getvalue()

        # Template generator creates all incident templates by design. When
        # selected incident codes are provided by the web UI, retain only those.
        if module_path == "src.accuracy_testing.scripts.accuracy_template_generator":
            processing_cfg = config_snapshot.get("processing")
            paths_cfg = config_snapshot.get("paths")
            selected_codes = (
                processing_cfg.get("incident_codes")
                if isinstance(processing_cfg, dict)
                else None
            )
            output_dir = (
                paths_cfg.get("output", {}).get("directory")
                if isinstance(paths_cfg, dict)
                else None
            )
            if isinstance(selected_codes, list) and selected_codes and isinstance(output_dir, str):
                allowed = {str(code).strip() for code in selected_codes if str(code).strip()}
                removed_count, scanned_count = _filter_template_outputs(output_dir, allowed)
                _publish_log_line(
                    (
                        f"Template filter applied: kept {len(allowed)} selected incident(s); "
                        f"removed {removed_count} of {scanned_count} generated template file(s)."
                    )
                )
                output = output_capture.getvalue()

        # ── Success ─────────────────────────────────────────────────────────
        _sync_update_status(job_id, "success", output_files=[], log_output=output)
        _publish_progress(_publish, estimator.on_terminal())
        _publish({"type": "status", "data": "success"})
        return {"status": "success", "output_files": []}

    except Exception as exc:
        # Ensure stdout is always restored on unexpected error.
        sys.stdout = old_stdout
        sys.stderr = old_stderr

        # Flush any partial output.
        output_capture.flush()
        partial_output = output_capture.getvalue()
        for line in partial_output.splitlines():
            if line.strip():
                _publish({"type": "log", "data": line})

        error_str = f"{type(exc).__name__}: {exc}"
        _publish({"type": "log", "data": error_str})
        _publish_progress(_publish, estimator.on_terminal())
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
    _publish({"type": "progress", "data": 5})
    heartbeat_stop = threading.Event()
    heartbeat_thread = _start_heartbeat(
        lambda line: _publish({"type": "log", "data": line}),
        heartbeat_stop,
    )

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
            _publish({"type": "progress", "data": int((idx / total) * 100)})
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
            _publish({"type": "progress", "data": int((idx / total) * 100)})
            failed = True
            if stop_on_error:
                break

    final_status = "failed" if failed else "success"
    _publish({"type": "progress", "data": 100})
    _publish({"type": "status", "data": final_status})
    _sync_update_status(
        job_id,
        final_status,
        error_message="Incident run completed with failures." if failed else None,
        log_output=full_output.getvalue(),
    )

    # Clean up temp YAML files.
    heartbeat_stop.set()
    if heartbeat_thread.is_alive():
        heartbeat_thread.join(timeout=1.0)

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

"""
Reconciliation Tasks
====================

Celery task that executes a scheduled reconciliation — generating DTF
extraction configs, polling for the resulting CSV files, running a fixed
subset of validation scripts across two different date windows, and
concluding with data_push to template files.

The ``run_reconciliation`` task phases:

1. **DTF generation (rec window)** — trade-by-trade scripts.
2. **DTF generation (lookback window)** — inconsistent ID scripts.
3. **CSV polling** — wait for external extraction to deposit files.
4. **Trade-by-trade validation** — buyer/seller ID, FTBDM/FTSDM.
5. **Inconsistent ID validation** — inconsistent buyer/seller ID.
6. **data_push** — push all validated results to template files.

.. note::

   The boundary between phases 2 and 3 is the designed swap point for
   when extraction migrates from DTF config generation to direct
   Python/API calls.  Only phases 1–3 would change.
"""

import asyncio
import contextlib
import importlib
import io
import json
import logging
import sys
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import redis as redis_lib
from celery import Task

from api.config import get_settings
from api.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)

# Lock protecting global sys.argv mutations across concurrent Celery tasks.
_argv_lock = threading.Lock()

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: Maximum time (seconds) to wait for extract CSV files before failing.
EXTRACT_POLL_TIMEOUT_SECONDS = 1800  # 30 minutes

#: Poll interval (seconds) between CSV file checks.
EXTRACT_POLL_INTERVAL_SECONDS = 60

#: Mapping from validation script name → period_extract_generator --validation-type value.
_SCRIPT_TO_EXTRACT_TYPE: dict[str, str] = {
    "buyer_id_validation": "buyer_id",
    "seller_id_validation": "seller_id",
    "validate_ftbdm": "fund_trade_buyer_dm",
    "validate_ftsdm": "fund_trade_seller_dm",
    "inconsistent_buyer_id_validation": "inconsistent_buyer_id",
    "inconsistent_seller_id_validation": "inconsistent_seller_id",
}

#: Mapping from script name → importable module path.
_REC_SCRIPT_MODULES: dict[str, str] = {
    "buyer_id_validation": "src.accuracy_testing.scripts.buyer_id_validation",
    "seller_id_validation": "src.accuracy_testing.scripts.seller_id_validation",
    "validate_ftbdm": "src.accuracy_testing.scripts.validate_ftbdm",
    "validate_ftsdm": "src.accuracy_testing.scripts.validate_ftsdm",
    "inconsistent_buyer_id_validation": "src.accuracy_testing.scripts.inconsistent_buyer_id_validation",
    "inconsistent_seller_id_validation": "src.accuracy_testing.scripts.inconsistent_seller_id_validation",
    "data_push": "src.accuracy_testing.scripts.data_push",
}

#: Trade-by-trade scripts use rec_period_days window.
_TRADE_BY_TRADE_SCRIPTS: frozenset[str] = frozenset(
    {
        "buyer_id_validation",
        "seller_id_validation",
        "validate_ftbdm",
        "validate_ftsdm",
    }
)

#: Inconsistent ID scripts use lookback_days window.
_INCONSISTENT_ID_SCRIPTS: frozenset[str] = frozenset(
    {
        "inconsistent_buyer_id_validation",
        "inconsistent_seller_id_validation",
    }
)

#: Execution order for reconciliation scripts.
_REC_EXECUTION_ORDER: list[str] = [
    "buyer_id_validation",
    "seller_id_validation",
    "validate_ftbdm",
    "validate_ftsdm",
    "inconsistent_buyer_id_validation",
    "inconsistent_seller_id_validation",
]


# ---------------------------------------------------------------------------
# Async DB-update helper (same pattern as pipeline_tasks)
# ---------------------------------------------------------------------------


async def _update_status_async(
    job_id: str,
    status: str,
    error_message: str | None = None,
    output_files: list[str] | None = None,
    log_output: str | None = None,
) -> None:
    """Open a fresh async DB session and update the job status."""
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
    """Synchronous wrapper that calls ``_update_status_async`` via asyncio.run."""
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
# Config builders
# ---------------------------------------------------------------------------


def _build_validation_config(
    script_name: str,
    extracts_dir: str,
    templates_dir: str,
    output_dir: str,
    logs_dir: str,
) -> dict:
    """Build a batch-mode config dict for a validation script."""
    return {
        "mode": "batch",
        "batch": {
            "paths": {
                "input_directory": extracts_dir,
                "output_directory": output_dir,
                "template_directory": templates_dir,
                "log_output": logs_dir,
            }
        },
    }


def _build_data_push_config(output_dir: str) -> dict:
    """Build a config dict for data_push."""
    return {
        "paths": {
            "input": {"directory": output_dir},
        },
    }


def _write_temp_yaml(config: dict) -> str:
    """Serialise ``config`` to a temporary YAML file and return its path."""
    import tempfile

    import yaml

    shared_tmp = Path("/app/data/tmp")
    shared_tmp.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".yaml",
        dir=shared_tmp,
        delete=False,
        encoding="utf-8",
    ) as fh:
        yaml.dump(config, fh, default_flow_style=False, allow_unicode=True)
        return fh.name


def _run_script(
    script_name: str,
    module_path: str,
    config: dict,
    publish: Any,
    full_output: io.StringIO,
    step_label: str,
) -> bool:
    """Import and run a single validation script, returning True on success.

    Args:
        script_name: Key identifying the script.
        module_path: Importable dotted module path.
        config: Configuration dict to write as YAML.
        publish: Callable to publish log/status messages to Redis.
        full_output: StringIO accumulator for the complete log.
        step_label: Prefix label for log messages (e.g. "[4/6]").

    Returns:
        ``True`` if the script completed successfully, ``False`` otherwise.
    """
    header = f"{step_label} Running {script_name}..."
    publish({"type": "log", "data": header})
    full_output.write(header + "\n")

    tmp_path = _write_temp_yaml(config)
    argv = ["--config", tmp_path, "--log-level", "INFO"]

    try:
        module = importlib.import_module(module_path)
        script_buffer = io.StringIO()

        with _argv_lock:
            old_argv = sys.argv
            sys.argv = [module_path] + argv
            try:
                with contextlib.redirect_stdout(script_buffer), \
                     contextlib.redirect_stderr(script_buffer):
                    module.main(argv)
            finally:
                sys.argv = old_argv

        output_text = script_buffer.getvalue()
        for line in output_text.splitlines():
            if line.strip():
                publish({"type": "log", "data": line})
        full_output.write(output_text)

        publish({"type": "log", "data": f"  ✓ {script_name} completed."})
        full_output.write(f"  ✓ {script_name} completed.\n")
        return True

    except SystemExit as exc:
        if exc.code in (None, 0):
            publish({"type": "log", "data": f"  ✓ {script_name} completed."})
            full_output.write(f"  ✓ {script_name} completed.\n")
            return True
        error_msg = f"  ✗ {script_name} exited with code {exc.code}."
        publish({"type": "log", "data": error_msg})
        full_output.write(error_msg + "\n")
        return False

    except Exception as exc:  # noqa: BLE001
        error_msg = f"  ✗ {script_name} failed: {exc}"
        publish({"type": "log", "data": error_msg})
        full_output.write(error_msg + "\n")
        return False

    finally:
        # Clean up temp YAML.
        try:
            Path(tmp_path).unlink(missing_ok=True)
        except Exception:  # noqa: BLE001
            pass


# ---------------------------------------------------------------------------
# Reconciliation Celery task
# ---------------------------------------------------------------------------


@celery_app.task(bind=True, name="api.tasks.reconciliation_tasks.run_reconciliation")
def run_reconciliation(
    self: Task,
    job_id: str,
    config_snapshot: dict,
) -> dict[str, Any]:
    """Execute a scheduled reconciliation.

    Args:
        job_id: UUID string of the parent job.
        config_snapshot: Dict containing ``rec_period_days``,
            ``lookback_days``, ``selected_scripts``, ``config_overrides``,
            and ``stop_on_error``.

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

    # ── Mark running ────────────────────────────────────────────────────────
    _sync_update_status(job_id, "running")
    _publish({"type": "status", "data": "running"})

    rec_period_days: int = config_snapshot["rec_period_days"]
    lookback_days: int = config_snapshot["lookback_days"]
    selected_scripts: list[str] = config_snapshot["selected_scripts"]
    overrides: dict = config_snapshot.get("config_overrides") or {}
    stop_on_error: bool = config_snapshot.get("stop_on_error", True)

    now = datetime.now(tz=timezone.utc)
    rec_end = now.date()
    rec_start = (now - timedelta(days=rec_period_days)).date()
    lookback_start = (now - timedelta(days=lookback_days)).date()

    # Resolve paths — reconciliation uses a dedicated rec/ directory.
    root = Path("/app/data/reconciliation") / now.strftime("%Y%m%d_%H%M%S")
    extracts_dir = overrides.get("extracts", str(root / "extracts"))
    templates_dir = overrides.get("templates", str(root / "templates"))
    output_dir = overrides.get("output", str(root / "output"))
    logs_dir = overrides.get("logs", str(root / "logs"))
    dtf_dir = overrides.get("dtf", str(root / "dtf"))

    for d in (extracts_dir, templates_dir, output_dir, logs_dir, dtf_dir):
        Path(d).mkdir(parents=True, exist_ok=True)

    full_output = io.StringIO()
    results: list[dict] = []
    failed = False
    expected_csvs: list[str] = []

    # Order selected_scripts according to fixed execution order.
    ordered_scripts = [
        s for s in _REC_EXECUTION_ORDER if s in selected_scripts
    ]

    # ── Phase 1 & 2: DTF config generation ──────────────────────────────────
    _publish({"type": "log", "data": "═══ Phase 1: Generating DTF extraction configs ═══"})
    full_output.write("═══ Phase 1: Generating DTF extraction configs ═══\n")

    for script_name in ordered_scripts:
        extract_type = _SCRIPT_TO_EXTRACT_TYPE.get(script_name)
        if extract_type is None:
            continue

        # Choose the appropriate date window.
        if script_name in _TRADE_BY_TRADE_SCRIPTS:
            start = str(rec_start)
            end = str(rec_end)
            window_label = f"rec window ({rec_period_days}d)"
        else:
            start = str(lookback_start)
            end = str(rec_end)
            window_label = f"lookback window ({lookback_days}d)"

        msg = f"  Generating DTF for {script_name} ({window_label}: {start} to {end})"
        _publish({"type": "log", "data": msg})
        full_output.write(msg + "\n")

        try:
            module = importlib.import_module(
                "src.accuracy_testing.scripts.period_extract_generator"
            )
            gen_argv = [
                "--validation-type", extract_type,
                "--start-date", start,
                "--end-date", end,
                "--output-dir", dtf_dir,
            ]
            gen_buffer = io.StringIO()

            with _argv_lock:
                old_argv = sys.argv
                sys.argv = ["period_extract_generator"] + gen_argv
                try:
                    with contextlib.redirect_stdout(gen_buffer), \
                         contextlib.redirect_stderr(gen_buffer):
                        module.main()
                finally:
                    sys.argv = old_argv

            gen_output = gen_buffer.getvalue()
            for line in gen_output.splitlines():
                if line.strip():
                    _publish({"type": "log", "data": f"    {line}"})
            full_output.write(gen_output)

            # Record expected CSV paths (DTF runner creates .csv alongside .dtf).
            for csv_file in Path(dtf_dir).glob(f"*{extract_type}*.csv"):
                expected_csvs.append(str(csv_file))

            results.append({"script": f"extract:{script_name}", "status": "success"})

        except SystemExit as exc:
            if exc.code in (None, 0):
                results.append({"script": f"extract:{script_name}", "status": "success"})
            else:
                error_msg = f"  ✗ DTF generation for {script_name} exited with code {exc.code}."
                _publish({"type": "log", "data": error_msg})
                full_output.write(error_msg + "\n")
                results.append({"script": f"extract:{script_name}", "status": "failed"})
                failed = True
                if stop_on_error:
                    break

        except Exception as exc:  # noqa: BLE001
            error_msg = f"  ✗ DTF generation for {script_name} failed: {exc}"
            _publish({"type": "log", "data": error_msg})
            full_output.write(error_msg + "\n")
            results.append({"script": f"extract:{script_name}", "status": "failed"})
            failed = True
            if stop_on_error:
                break

    if failed and stop_on_error:
        _publish({"type": "status", "data": "failed"})
        _sync_update_status(
            job_id, "failed",
            error_message="DTF generation failed.",
            log_output=full_output.getvalue(),
        )
        return {"status": "failed", "results": results}

    # ── Phase 3: CSV polling ────────────────────────────────────────────────
    # This is the designed swap point: when extraction migrates from DTF
    # config generation to direct Python/API calls, replace phases 1–3.
    _publish({"type": "log", "data": "═══ Phase 2: Waiting for extract CSV files ═══"})
    full_output.write("═══ Phase 2: Waiting for extract CSV files ═══\n")

    if expected_csvs:
        deadline = time.monotonic() + EXTRACT_POLL_TIMEOUT_SECONDS
        while time.monotonic() < deadline:
            missing = [p for p in expected_csvs if not Path(p).exists()]
            if not missing:
                msg = "  All extract CSV files found."
                _publish({"type": "log", "data": msg})
                full_output.write(msg + "\n")
                break
            for m in missing:
                _publish({"type": "log", "data": f"  Waiting for extract: {Path(m).name}"})
            time.sleep(EXTRACT_POLL_INTERVAL_SECONDS)
        else:
            missing = [p for p in expected_csvs if not Path(p).exists()]
            if missing:
                error_msg = (
                    f"  ✗ Timed out after {EXTRACT_POLL_TIMEOUT_SECONDS}s waiting for "
                    f"extract files: {[Path(p).name for p in missing]}"
                )
                _publish({"type": "log", "data": error_msg})
                full_output.write(error_msg + "\n")
                _publish({"type": "status", "data": "failed"})
                _sync_update_status(
                    job_id, "failed",
                    error_message=f"Extract timeout: {[Path(p).name for p in missing]}",
                    log_output=full_output.getvalue(),
                )
                return {"status": "failed", "results": results}
    else:
        msg = "  No extract CSV files expected — skipping poll."
        _publish({"type": "log", "data": msg})
        full_output.write(msg + "\n")

    # ── Phase 4 & 5: Validation scripts ─────────────────────────────────────
    _publish({"type": "log", "data": "═══ Phase 3: Running validation scripts ═══"})
    full_output.write("═══ Phase 3: Running validation scripts ═══\n")

    total_scripts = len(ordered_scripts)
    for idx, script_name in enumerate(ordered_scripts, 1):
        module_path = _REC_SCRIPT_MODULES.get(script_name)
        if module_path is None:
            continue

        config = _build_validation_config(
            script_name, extracts_dir, templates_dir, output_dir, logs_dir,
        )

        step_label = f"[{idx}/{total_scripts}]"
        success = _run_script(
            script_name, module_path, config,
            _publish, full_output, step_label,
        )
        results.append({"script": script_name, "status": "success" if success else "failed"})

        if not success:
            failed = True
            if stop_on_error:
                break

    if failed and stop_on_error:
        _publish({"type": "status", "data": "failed"})
        _sync_update_status(
            job_id, "failed",
            error_message="Validation failed.",
            log_output=full_output.getvalue(),
        )
        return {"status": "failed", "results": results}

    # ── Phase 6: data_push ──────────────────────────────────────────────────
    _publish({"type": "log", "data": "═══ Phase 4: Running data_push ═══"})
    full_output.write("═══ Phase 4: Running data_push ═══\n")

    data_push_module = _REC_SCRIPT_MODULES["data_push"]
    data_push_config = _build_data_push_config(output_dir)
    success = _run_script(
        "data_push", data_push_module, data_push_config,
        _publish, full_output, "[data_push]",
    )
    results.append({"script": "data_push", "status": "success" if success else "failed"})
    if not success:
        failed = True

    # ── Final status ────────────────────────────────────────────────────────
    final_status = "failed" if failed else "success"
    _publish({"type": "status", "data": final_status})
    _sync_update_status(
        job_id,
        final_status,
        error_message="Reconciliation completed with failures." if failed else None,
        log_output=full_output.getvalue(),
    )

    return {"status": final_status, "results": results}

"""
Pipeline Tasks
==============

Celery task that executes an accuracy testing pipeline — a sequence of
scripts run one after another, sharing the same FY/Q and directory layout.

The ``run_pipeline`` task:

1. Resolves directory paths from the pipeline's fiscal year and quarter.
2. Iterates through ``selected_scripts`` in order.
3. For each script, builds a config YAML, imports the module, and calls
   ``module.main(argv)`` — capturing output and streaming logs to Redis.
4. Stops on first failure if ``stop_on_error`` is ``True``.
5. Updates the parent job status to ``success`` or ``failed`` on completion.
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
# Script registry (subset relevant to pipelines)
# ---------------------------------------------------------------------------

_PIPELINE_SCRIPT_MODULES: dict[str, str] = {
    "accuracy_template_generator": "src.accuracy_testing.scripts.accuracy_template_generator",
    "sql_extract_generator": "src.accuracy_testing.scripts.sql_extract_generator",
    "collate_csv_extracts": "src.accuracy_testing.scripts.collate_csv_extracts",
    "buyer_id_validation": "src.accuracy_testing.scripts.buyer_id_validation",
    "seller_id_validation": "src.accuracy_testing.scripts.seller_id_validation",
    "inconsistent_buyer_id_validation": "src.accuracy_testing.scripts.inconsistent_buyer_id_validation",
    "inconsistent_seller_id_validation": "src.accuracy_testing.scripts.inconsistent_seller_id_validation",
    "validate_ftbdm": "src.accuracy_testing.scripts.validate_ftbdm",
    "validate_ftsdm": "src.accuracy_testing.scripts.validate_ftsdm",
    "incorrect_net_amount_validation": "src.accuracy_testing.scripts.incorrect_net_amount_validation",
    "non_zero_net_quantity": "src.accuracy_testing.scripts.non_zero_net_quantity",
    "non_zero_net_amount": "src.accuracy_testing.scripts.non_zero_net_amount",
    "incorrect_time": "src.accuracy_testing.scripts.incorrect_time",
    "data_push": "src.accuracy_testing.scripts.data_push",
}

# Validation scripts use batch mode config.
_VALIDATION_SCRIPTS: frozenset[str] = frozenset(
    {
        "buyer_id_validation",
        "seller_id_validation",
        "inconsistent_buyer_id_validation",
        "inconsistent_seller_id_validation",
        "validate_ftbdm",
        "validate_ftsdm",
        "incorrect_net_amount_validation",
        "non_zero_net_quantity",
        "non_zero_net_amount",
        "incorrect_time",
    }
)


# ---------------------------------------------------------------------------
# Async DB-update helper
# ---------------------------------------------------------------------------


async def _update_status_async(
    job_id: str,
    status: str,
    error_message: str | None = None,
    output_files: list[str] | None = None,
    log_output: str | None = None,
) -> None:
    """Open a fresh async DB session and update the job status.

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
    fiscal_year: str,
    quarter: str,
    extracts_dir: str,
    templates_dir: str,
    output_dir: str,
    logs_dir: str,
) -> dict:
    """Build a batch-mode YAML config dict for a validation script.

    Args:
        script_name: The script identifier.
        fiscal_year: Fiscal year string.
        quarter: Quarter string.
        extracts_dir: Path to the extracts directory.
        templates_dir: Path to the templates directory.
        output_dir: Path to the output directory.
        logs_dir: Path to the logs directory.

    Returns:
        Configuration dict suitable for writing to YAML.
    """
    return {
        "mode": "batch",
        "testing_period": {
            "fiscal_year": fiscal_year,
            "quarter": quarter,
        },
        "batch": {
            "paths": {
                "input_directory": extracts_dir,
                "output_directory": output_dir,
                "template_directory": templates_dir,
                "log_output": logs_dir,
            }
        },
    }


def _build_utility_config(
    script_name: str,
    fiscal_year: str,
    quarter: str,
    kaizen_dir: str,
    extracts_dir: str,
    templates_dir: str,
    output_dir: str,
    logs_dir: str,
) -> dict:
    """Build a config dict for a utility script.

    Args:
        script_name: The script identifier.
        fiscal_year: Fiscal year string.
        quarter: Quarter string.
        kaizen_dir: Path to the kaizen directory (consolidated source CSVs).
        extracts_dir: Path to the extracts directory.
        templates_dir: Path to the templates directory.
        output_dir: Path to the output directory.
        logs_dir: Path to the logs directory.

    Returns:
        Configuration dict suitable for writing to YAML.
    """
    config: dict = {
        "testing_period": {
            "fiscal_year": fiscal_year,
            "quarter": quarter,
        },
    }

    if script_name == "sql_extract_generator":
        config["paths"] = {"output": {"directory": extracts_dir}}
    elif script_name == "accuracy_template_generator":
        config["paths"] = {
            "input": {"directory": kaizen_dir},
            "output": {"directory": templates_dir},
        }
    elif script_name == "collate_csv_extracts":
        config["paths"] = {
            "input": {"directory": extracts_dir},
            "output": {"directory": extracts_dir},
        }
    elif script_name == "data_push":
        config["paths"] = {
            "input": {"directory": output_dir},
        }

    return config


def _write_temp_yaml(config: dict) -> str:
    """Serialise ``config`` to a temporary YAML file and return its path.

    Args:
        config: Configuration dictionary to serialise.

    Returns:
        Absolute filesystem path to the written temporary file.
    """
    import tempfile

    import yaml

    shared_tmp = Path(get_settings().data_dir) / "tmp"
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


# ---------------------------------------------------------------------------
# Pipeline Celery task
# ---------------------------------------------------------------------------


@celery_app.task(bind=True, name="api.tasks.pipeline_tasks.run_pipeline")
def run_pipeline(
    self: Task,
    job_id: str,
    config_snapshot: dict,
) -> dict[str, Any]:
    """Execute an accuracy testing pipeline sequentially.

    Each script in ``selected_scripts`` is imported, configured, and run.
    Logs are streamed to Redis for live WebSocket viewing.

    Args:
        job_id: UUID string of the parent pipeline job.
        config_snapshot: Dict containing ``fiscal_year``, ``quarter``,
            ``selected_scripts``, ``config_overrides``, and ``stop_on_error``.

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

    def _publish_progress(percent: int) -> None:
        bounded = max(0, min(100, percent))
        _publish({"type": "progress", "data": bounded})

    # ── Mark running ────────────────────────────────────────────────────────
    _sync_update_status(job_id, "running")
    _publish({"type": "status", "data": "running"})
    _publish_progress(5)

    fiscal_year = config_snapshot["fiscal_year"]
    quarter = config_snapshot["quarter"]
    selected_scripts: list[str] = config_snapshot["selected_scripts"]
    overrides: dict = config_snapshot.get("config_overrides") or {}
    stop_on_error: bool = config_snapshot.get("stop_on_error", True)

    # Resolve paths.
    root = Path(get_settings().data_dir) / fiscal_year / quarter
    kaizen_dir = overrides.get("kaizen", str(root / "kaizen"))
    extracts_dir = overrides.get("extracts", str(root / "extracts"))
    templates_dir = overrides.get("templates", str(root / "templates"))
    output_dir = overrides.get("output", str(root / "output"))
    logs_dir = overrides.get("logs", str(root / "logs"))

    # Ensure directories exist.
    for d in (kaizen_dir, extracts_dir, templates_dir, output_dir, logs_dir):
        Path(d).mkdir(parents=True, exist_ok=True)

    full_output = io.StringIO()
    results: list[dict] = []
    failed = False
    extract_gen_just_ran = False
    total_scripts = max(len(selected_scripts), 1)

    for idx, script_name in enumerate(selected_scripts, 1):
        # ── Pause after Extract Generator, before Collate ───────────────────
        if extract_gen_just_ran and script_name != "sql_extract_generator":
            extract_gen_just_ran = False
            # Determine expected extract CSVs from all incident-related scripts
            # that appear later in the pipeline (i.e. validation scripts + collate).
            _INCIDENT_CODES: dict[str, list[str]] = {
                "buyer_id_validation": ["7_35", "7_37", "7_39"],
                "seller_id_validation": ["16_19", "16_21", "16_23"],
                "inconsistent_buyer_id_validation": ["7_66"],
                "inconsistent_seller_id_validation": ["16_20"],
                "validate_ftbdm": ["12_17"],
                "validate_ftsdm": ["21_17"],
                "incorrect_net_amount_validation": ["35_3"],
                "non_zero_net_quantity": ["7_6"],
                "non_zero_net_amount": ["7_42"],
            }
            expected_codes: list[str] = []
            for future_script in selected_scripts[idx - 1 :]:
                for code in _INCIDENT_CODES.get(future_script, []):
                    if code not in expected_codes:
                        expected_codes.append(code)

            if expected_codes:
                expected_files = [
                    Path(extracts_dir) / f"{code}_{fiscal_year}_{quarter}_extract.csv"
                    for code in expected_codes
                ]

                wait_msg = (
                    f"Waiting for {len(expected_files)} System i CSV extract(s) "
                    f"in {extracts_dir}…"
                )
                _publish({"type": "log", "data": wait_msg})
                full_output.write(wait_msg + "\n")
                _sync_update_status(job_id, "waiting")
                _publish({"type": "waiting", "data": wait_msg})

                while True:
                    missing = [f for f in expected_files if not f.exists()]
                    if not missing:
                        found_msg = (
                            "All expected extract CSVs detected — resuming pipeline."
                        )
                        _publish({"type": "log", "data": found_msg})
                        full_output.write(found_msg + "\n")
                        _sync_update_status(job_id, "running")
                        _publish({"type": "status", "data": "running"})
                        break

                    heartbeat = (
                        f"Waiting for System i CSV extracts… "
                        f"{len(missing)}/{len(expected_files)} still missing."
                    )
                    _publish({"type": "waiting", "data": heartbeat})
                    _publish_progress(max(10, int(((idx - 1) / total_scripts) * 90)))
                    time.sleep(60)

        module_path = _PIPELINE_SCRIPT_MODULES.get(script_name)
        if module_path is None:
            msg = f"[{idx}/{len(selected_scripts)}] Unknown script '{script_name}' — skipping."
            _publish({"type": "log", "data": msg})
            full_output.write(msg + "\n")
            results.append({"script": script_name, "status": "skipped"})
            _publish_progress(max(10, int((idx / total_scripts) * 90)))
            continue

        header = f"[{idx}/{len(selected_scripts)}] Running {script_name}..."
        _publish({"type": "log", "data": header})
        full_output.write(header + "\n")

        # Build config.
        if script_name in _VALIDATION_SCRIPTS:
            config = _build_validation_config(
                script_name,
                fiscal_year,
                quarter,
                extracts_dir,
                templates_dir,
                output_dir,
                logs_dir,
            )
        else:
            config = _build_utility_config(
                script_name,
                fiscal_year,
                quarter,
                kaizen_dir,
                extracts_dir,
                templates_dir,
                output_dir,
                logs_dir,
            )

        tmp_path = _write_temp_yaml(config)
        argv = ["--config", tmp_path, "--log-level", "INFO"]

        try:
            module = importlib.import_module(module_path)
            script_buffer = io.StringIO()

            with _argv_lock:
                old_argv = sys.argv
                sys.argv = [module_path] + argv
                try:
                    with contextlib.redirect_stdout(
                        script_buffer
                    ), contextlib.redirect_stderr(script_buffer):
                        module.main(argv)
                finally:
                    sys.argv = old_argv

            output_text = script_buffer.getvalue()
            for line in output_text.splitlines():
                if line.strip():
                    _publish({"type": "log", "data": line})
            full_output.write(output_text)

            results.append({"script": script_name, "status": "success"})
            _publish({"type": "log", "data": f"  ✓ {script_name} completed."})
            full_output.write(f"  ✓ {script_name} completed.\n")
            _publish_progress(max(10, int((idx / total_scripts) * 90)))

            if script_name == "sql_extract_generator":
                extract_gen_just_ran = True

        except SystemExit as exc:
            if exc.code in (None, 0):
                results.append({"script": script_name, "status": "success"})
                _publish({"type": "log", "data": f"  ✓ {script_name} completed."})
                full_output.write(f"  ✓ {script_name} completed.\n")
                _publish_progress(max(10, int((idx / total_scripts) * 90)))

                if script_name == "sql_extract_generator":
                    extract_gen_just_ran = True
            else:
                error_msg = f"  ✗ {script_name} exited with code {exc.code}."
                _publish({"type": "log", "data": error_msg})
                full_output.write(error_msg + "\n")
                results.append(
                    {"script": script_name, "status": "failed", "exit_code": exc.code}
                )
                _publish_progress(max(10, int((idx / total_scripts) * 90)))
                failed = True
                if stop_on_error:
                    break

        except Exception as exc:  # noqa: BLE001
            error_msg = f"  ✗ {script_name} failed: {exc}"
            _publish({"type": "log", "data": error_msg})
            full_output.write(error_msg + "\n")
            results.append(
                {"script": script_name, "status": "failed", "error": str(exc)}
            )
            _publish_progress(max(10, int((idx / total_scripts) * 90)))
            failed = True
            if stop_on_error:
                break

    # ── Final status ────────────────────────────────────────────────────────
    final_status = "failed" if failed else "success"
    _publish_progress(100)
    _publish({"type": "status", "data": final_status})
    _sync_update_status(
        job_id,
        final_status,
        error_message=f"Pipeline completed with failures." if failed else None,
        log_output=full_output.getvalue(),
    )

    return {"status": final_status, "results": results}

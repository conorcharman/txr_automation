"""
Script Runner Service
=====================

Service layer that converts typed API request schemas into ``(module_path, argv,
config_snapshot)`` tuples ready for dispatch to the ``run_script`` Celery task.

Each ``build_*`` method:

1. Validates the ``script_name`` against the relevant set of registered scripts.
2. Serialises the request fields into a config dict matching the script's YAML
   template structure.
3. Writes the config dict to a temporary YAML file on disk (``delete=False`` so
   the Celery worker process can read it after this method returns).
4. Returns ``(module_path, argv, config_snapshot)`` where ``argv`` is always
   ``["--config", "<tmpfile_path>", "--log-level", "<level>"]``.

Usage::

    service = ScriptRunnerService()
    module_path, argv, snapshot = service.build_accuracy_argv(req)
    job = await job_service.create_job(db, req.script_name, snapshot)
    run_script.delay(str(job.id), module_path, argv, snapshot)

Note:
    ``_SCRIPT_MODULES`` mirrors the registry in ``api/routers/jobs.py``.
    Both dicts must be kept in sync when adding new scripts.
"""

import logging
import os
import tempfile
from pathlib import Path
from typing import Union

import yaml
from fastapi import HTTPException

from api.config import get_settings
from api.schemas.accuracy import RunAllRequest, RunValidationRequest
from api.schemas.firds import FirdsBackfillRequest, FirdsCheckRequest, FirdsRefreshRequest
from api.schemas.gleif import GleifBackfillRequest, GleifCheckRequest, GleifRefreshRequest
from api.schemas.replay import (
    ReplayMergeRequest,
    ReplayPhase2Request,
    ReplayPhase3FinalRequest,
    ReplayPhase3Request,
)
from api.schemas.utilities import XlsxConverterRequest, XmlConverterRequest

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Script registry (mirrors api.routers.jobs.SCRIPT_MODULES)
# ---------------------------------------------------------------------------

#: Maps every registered script name to its fully-qualified Python module path.
#: Must be kept in sync with ``SCRIPT_MODULES`` in ``api/routers/jobs.py``.
_SCRIPT_MODULES: dict[str, str] = {
    # Accuracy Testing — validation scripts
    "buyer_id_validation":               "src.accuracy_testing.scripts.buyer_id_validation",
    "seller_id_validation":              "src.accuracy_testing.scripts.seller_id_validation",
    "inconsistent_buyer_id_validation":  "src.accuracy_testing.scripts.inconsistent_buyer_id_validation",
    "inconsistent_seller_id_validation": "src.accuracy_testing.scripts.inconsistent_seller_id_validation",
    "validate_ftbdm":                    "src.accuracy_testing.scripts.validate_ftbdm",
    "validate_ftsdm":                    "src.accuracy_testing.scripts.validate_ftsdm",
    "incorrect_net_amount_validation":   "src.accuracy_testing.scripts.incorrect_net_amount_validation",
    "non_zero_net_quantity":             "src.accuracy_testing.scripts.non_zero_net_quantity",
    "non_zero_net_amount":               "src.accuracy_testing.scripts.non_zero_net_amount",
    # Accuracy Testing — utility scripts
    "run_all_validations":               "src.accuracy_testing.scripts.run_all_validations",
    "sql_extract_generator":             "src.accuracy_testing.scripts.sql_extract_generator",
    "accuracy_template_generator":       "src.accuracy_testing.scripts.accuracy_template_generator",
    "collate_csv_extracts":              "src.accuracy_testing.scripts.collate_csv_extracts",
    "data_push":                         "src.accuracy_testing.scripts.data_push",
    # Replay
    "replay_phase2":                     "src.replay.phase_2_processor",
    "replay_phase3":                     "src.replay.phase_3_processor",
    "replay_phase3_final":               "src.replay.phase_3_final_lookup",
    "replay_merge_inconsistent":         "src.replay.merge_inconsistent_ids",
    # FIRDS
    "firds_refresh":                     "src.firds.scripts.refresh_cache",
    "firds_check":                       "src.firds.scripts.check_reportability",
    "firds_backfill":                    "src.firds.scripts.backfill",
    # GLEIF
    "gleif_refresh":                     "src.gleif.scripts.refresh_cache",
    "gleif_check":                       "src.gleif.scripts.check_lei",
    "gleif_backfill":                    "src.gleif.scripts.backfill",
    # Utilities
    "xlsx_csv_converter":                "src.utils.xlsx_csv_converter",
    "xml_csv_converter":                 "src.utils.xml_csv_converter",
}

#: Script names accepted by the ``/api/accuracy/run`` endpoint.
#: Excludes ``run_all_validations`` which has its own dedicated endpoint.
ACCURACY_VALIDATION_SCRIPTS: frozenset[str] = frozenset(
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
        "sql_extract_generator",
        "accuracy_template_generator",
        "collate_csv_extracts",
        "data_push",
    }
)


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _write_temp_yaml(config: dict) -> str:
    """Validate paths, serialise ``config`` to a temporary YAML file, and return its path.

    Applies path traversal validation to all path-like string values in
    the config before writing.  The file is written with ``delete=False``
    so the Celery worker process can read it after this function returns.

    Temp files are placed in ``/app/data/tmp/`` rather than the system
    ``/tmp/`` because the API and Celery worker run in separate Docker
    containers that share the ``./data`` volume mount but not ``/tmp/``.

    Args:
        config: Configuration dictionary to serialise as YAML.

    Returns:
        Absolute filesystem path to the written temporary file.

    Raises:
        HTTPException: 400 if any path value contains traversal sequences.
    """
    _validate_paths(config)
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


def _resolve_module(script_name: str) -> str:
    """Return the module path for a registered script name.

    Args:
        script_name: Registered script identifier.

    Returns:
        Dotted Python module path string.

    Raises:
        HTTPException: 400 if ``script_name`` is not registered.
    """
    module_path = _SCRIPT_MODULES.get(script_name)
    if module_path is None:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown script '{script_name}'.",
        )
    return module_path


def _validate_path(value: str, field_name: str) -> str:
    """Reject path values containing traversal sequences.

    Checks both the raw input and the normalised form for ``..``
    components.  This catches traversal attempts regardless of whether
    ``os.path.normpath`` resolves them away.

    Args:
        value: Raw path string from the API request.
        field_name: Human-readable field name for error messages.

    Returns:
        The normalised path string.

    Raises:
        HTTPException: 400 if the path contains traversal sequences.
    """
    if ".." in value.split("/"):
        raise HTTPException(
            status_code=400,
            detail=f"Path traversal not allowed in '{field_name}'.",
        )
    normalised = os.path.normpath(value)
    if ".." in normalised.split(os.sep):
        raise HTTPException(
            status_code=400,
            detail=f"Path traversal not allowed in '{field_name}'.",
        )
    return normalised


def _validate_paths(config: dict, prefix: str = "") -> dict:
    """Recursively validate all string values in a config dict that look like paths.

    Applies ``_validate_path`` to any string value whose key ends with
    ``_directory``, ``_dir``, ``_file``, ``_input``, ``_output``, or
    ``parent_dir``.

    Args:
        config: Configuration dictionary (may be nested).
        prefix: Dot-separated key prefix for error messages.

    Returns:
        The same config dict with normalised path values.
    """
    _PATH_SUFFIXES = ("_directory", "_dir", "_file", "_input", "_output", "parent_dir")
    for key, value in config.items():
        full_key = f"{prefix}.{key}" if prefix else key
        if isinstance(value, dict):
            _validate_paths(value, full_key)
        elif isinstance(value, str) and any(key.endswith(s) for s in _PATH_SUFFIXES):
            config[key] = _validate_path(value, full_key)
    return config


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class ScriptRunnerService:
    """Converts API request bodies into argv lists for Celery task dispatch.

    Each ``build_*`` method accepts the corresponding Pydantic request schema
    and returns a tuple of ``(module_path, argv, config_snapshot)``.  The
    caller creates a Job row and dispatches ``run_script.delay()`` with these
    values.

    Temporary YAML configuration files are written to disk so that the Celery
    worker can locate them even when running in a separate process.
    """

    def build_accuracy_argv(
        self,
        req: RunValidationRequest,
    ) -> tuple[str, list[str], dict]:
        """Build argv for a single accuracy validation script.

        Writes a temporary YAML config file matching the ``buyer_validation_template.yaml``
        structure and returns ``["--config", "<path>", "--log-level", "<level>"]``
        as the argv list.

        Args:
            req: Validated ``RunValidationRequest`` from the HTTP request body.

        Returns:
            A tuple of ``(module_path, argv, config_snapshot)``.

        Raises:
            HTTPException: 400 if ``req.script_name`` is not a registered
                accuracy validation script.
        """
        if req.script_name not in ACCURACY_VALIDATION_SCRIPTS:
            raise HTTPException(
                status_code=400,
                detail=f"'{req.script_name}' is not a valid accuracy validation script.",
            )

        module_path = _resolve_module(req.script_name)

        config: dict = {
            "mode": req.mode,
            "testing_period": {
                "fiscal_year": req.testing_period.fiscal_year,
                "quarter": req.testing_period.quarter,
            },
        }

        if req.mode == "batch" and req.batch_config is not None:
            config["batch"] = {
                "paths": {
                    "input_directory": req.batch_config.input_directory,
                    "output_directory": req.batch_config.output_directory,
                    "template_directory": req.batch_config.template_directory,
                    "log_output": req.batch_config.log_output,
                    "tracker_files": req.batch_config.tracker_files,
                    "italian_tracker": req.batch_config.italian_tracker,
                    "main_tracker": req.batch_config.main_tracker,
                }
            }
        elif req.mode == "single" and req.single_config is not None:
            config["single"] = {
                "incident_code": req.single_config.incident_code,
                "paths": {
                    "input_file": req.single_config.input_file,
                    "template_file": req.single_config.template_file,
                    "output_file": req.single_config.output_file,
                    "template_id_column": req.single_config.template_id_column,
                    "template_type_column": req.single_config.template_type_column,
                    "log_output": req.single_config.log_output,
                    "tracker_files": req.single_config.tracker_files,
                },
            }

        tmp_path = _write_temp_yaml(config)
        argv = ["--config", tmp_path, "--log-level", req.log_level]

        logger.debug(
            "Wrote accuracy config to %s for script %s.", tmp_path, req.script_name
        )
        return module_path, argv, config

    def build_run_all_argv(
        self,
        req: RunAllRequest,
    ) -> tuple[str, list[str], dict]:
        """Build argv for the ``run_all_validations`` orchestrator script.

        Generates an individual batch YAML config for each requested validation
        type, then writes a top-level ``run_all`` config that references them.

        Args:
            req: Validated ``RunAllRequest`` from the HTTP request body.

        Returns:
            A tuple of ``(module_path, argv, config_snapshot)``.
        """
        module_path = _resolve_module("run_all_validations")

        validations: list[dict] = []
        for script_name in req.validation_types:
            script_module = _SCRIPT_MODULES.get(script_name)
            if script_module is None:
                logger.warning(
                    "Unknown validation type '%s' in RunAllRequest; skipping.", script_name
                )
                continue

            sub_config: dict = {
                "mode": "batch",
                "testing_period": {
                    "fiscal_year": req.testing_period.fiscal_year,
                    "quarter": req.testing_period.quarter,
                },
                "batch": {
                    "paths": {
                        "input_directory": req.input_directory,
                        "output_directory": req.output_directory,
                        "template_directory": req.template_directory,
                        "log_output": "logs",
                        "tracker_files": [],
                    }
                },
            }
            sub_config_path = _write_temp_yaml(sub_config)
            validations.append(
                {
                    "name": script_name,
                    "script_module": script_module,
                    "config_file": sub_config_path,
                    "enabled": True,
                }
            )

        run_all_config: dict = {"validations": validations}
        tmp_path = _write_temp_yaml(run_all_config)
        argv = ["--config", tmp_path, "--log-level", req.log_level]
        if req.stop_on_error:
            argv.append("--stop-on-error")

        logger.debug(
            "Wrote run_all config to %s for %d validation(s).",
            tmp_path,
            len(validations),
        )
        return module_path, argv, run_all_config

    def build_replay_argv(
        self,
        req: Union[
            ReplayPhase2Request,
            ReplayPhase3Request,
            ReplayPhase3FinalRequest,
            ReplayMergeRequest,
        ],
        script_name: str,
    ) -> tuple[str, list[str], dict]:
        """Build argv for a replay processing script.

        Constructs a YAML config that mirrors the relevant replay template
        (``phase2_template.yaml``, ``phase3_template.yaml``, etc.) from the
        simplified API request fields.

        Args:
            req: Validated replay request schema.
            script_name: Registered script identifier, e.g. ``"replay_phase2"``.

        Returns:
            A tuple of ``(module_path, argv, config_snapshot)``.

        Raises:
            HTTPException: 400 if ``script_name`` is not a registered replay script.
        """
        module_path = _resolve_module(script_name)

        config: dict

        if isinstance(req, ReplayPhase2Request):
            config = {
                "paths": {
                    "replay_input": req.input_file,
                    "replay_output": req.output_file,
                    "log_output": "logs",
                },
                "files": {
                    "replay_patterns": ["*.csv"],
                    "incident_pattern": f"{req.fiscal_year} {req.quarter} *.csv",
                },
                "processor": {
                    "batch_size": 50,
                    "log_level": req.log_level,
                },
            }

        elif isinstance(req, ReplayPhase3Request):
            config = {
                "paths": {
                    "replay_input": req.input_file,
                    "incident_files": req.feedback_file,
                    "replay_output": req.output_file,
                    "log_output": "logs",
                },
                "files": {
                    "replay_patterns": [
                        "Replay_*_PHASE 3_Inconsistent_IDs_Summary_FINAL.csv",
                        "Replay_*_PHASE 3_Inconsistent_Names_Summary_FINAL.csv",
                    ],
                    "incident_pattern": f"{req.fiscal_year} {req.quarter} *.csv",
                },
                "processor": {
                    "batch_size": 50,
                    "log_level": req.log_level,
                },
            }

        elif isinstance(req, ReplayPhase3FinalRequest):
            config = {
                "paths": {
                    "replay_input": req.input_file,
                    "replay_output": req.output_file,
                    "log_output": "logs",
                },
                "files": {
                    "replay_ids_pattern": "Replay_*_Inconsistent_IDs_Summary_*.csv",
                    "replay_names_pattern": "Replay_*_Inconsistent_Names_Summary_*.csv",
                },
                "processor": {
                    "batch_size": 100,
                    "log_level": req.log_level,
                },
            }

        else:  # ReplayMergeRequest
            config = {
                "paths": {
                    "input_dir": req.buyer_file,
                },
                "files": {
                    "ids_pattern": "Replay_*_Inconsistent_IDs_Summary_*.csv",
                    "names_pattern": "Replay_*_Inconsistent_Names_Summary_*.csv",
                },
                "processor": {
                    "log_level": req.log_level,
                },
            }

        tmp_path = _write_temp_yaml(config)
        argv = ["--config", tmp_path, "--log-level", req.log_level]

        logger.debug("Wrote replay config to %s for script %s.", tmp_path, script_name)
        return module_path, argv, config

    def build_firds_argv(
        self,
        req: Union[FirdsRefreshRequest, FirdsCheckRequest, FirdsBackfillRequest],
        script_name: str,
    ) -> tuple[str, list[str], dict]:
        """Build argv for a FIRDS script.

        Args:
            req: Validated FIRDS request schema.
            script_name: Registered script identifier, e.g. ``"firds_refresh"``.

        Returns:
            A tuple of ``(module_path, argv, config_snapshot)``.

        Raises:
            HTTPException: 400 if ``script_name`` is not a registered FIRDS script.
        """
        module_path = _resolve_module(script_name)
        settings = get_settings()

        config: dict

        if isinstance(req, FirdsRefreshRequest):
            db_path = req.db_path or str(settings.firds_db_path)
            # The CLI only accepts "full"; treat "auto" and "delta" as "full"
            # until the script gains native support for those modes.
            refresh_type = req.refresh_type if req.refresh_type == "full" else "full"
            config = {
                "refresh": {
                    "type": refresh_type,
                    "publication_date": req.publication_date,
                },
                "processor": {"log_level": req.log_level},
            }
            # Pass --config with an empty YAML to suppress auto-discovery of
            # config/local/firds_config.yaml (which may contain host-specific paths).
            tmp_path = _write_temp_yaml(config)
            argv = [
                "--type", refresh_type,
                "--db", db_path,
                "--config", tmp_path,
                "--log-level", req.log_level,
            ]
            if req.publication_date:
                argv.extend(["--date", req.publication_date])

        elif isinstance(req, FirdsCheckRequest):
            db_path = str(settings.firds_db_path)
            config = {
                "check": {
                    "mode": req.mode,
                    "isin": req.isin,
                    "input_file": req.input_file,
                    "output_file": req.output_file,
                },
                "processor": {"log_level": req.log_level},
            }
            tmp_path = _write_temp_yaml(config)
            argv = ["--db", db_path, "--config", tmp_path, "--log-level", req.log_level]
            if req.isin:
                argv.extend(["--isin", req.isin])
            if req.date:
                argv.extend(["--date", req.date])
            if req.mic:
                argv.extend(["--mic", req.mic])
            if req.input_file:
                argv.extend(["--input", req.input_file])
            if req.output_file:
                argv.extend(["--output", req.output_file])

        else:  # FirdsBackfillRequest
            db_path = req.db_path or str(settings.firds_db_path)
            config = {
                "backfill": {
                    "input_file": req.input_file,
                    "output_file": req.output_file,
                    "format": req.format,
                },
                "processor": {"log_level": req.log_level},
            }
            tmp_path = _write_temp_yaml(config)
            argv = [
                "--input", req.input_file,
                "--output", req.output_file,
                "--db", db_path,
                "--config", tmp_path,
                "--log-level", req.log_level,
            ]
            if req.format != "auto":
                argv.extend(["--format", req.format])
            if req.skip_refresh:
                argv.append("--skip-refresh")

        logger.debug("Built FIRDS argv %s for script %s.", argv, script_name)
        return module_path, argv, config

    def build_gleif_argv(
        self,
        req: Union[GleifRefreshRequest, GleifCheckRequest, GleifBackfillRequest],
        script_name: str,
    ) -> tuple[str, list[str], dict]:
        """Build argv for a GLEIF script.

        Args:
            req: Validated GLEIF request schema.
            script_name: Registered script identifier, e.g. ``"gleif_refresh"``.

        Returns:
            A tuple of ``(module_path, argv, config_snapshot)``.

        Raises:
            HTTPException: 400 if ``script_name`` is not a registered GLEIF script.
        """
        module_path = _resolve_module(script_name)
        settings = get_settings()
        db_path = str(settings.gleif_db_path)

        config: dict

        if isinstance(req, GleifRefreshRequest):
            # The CLI only accepts "full"; treat "auto" as "full".
            refresh_type = req.refresh_type if req.refresh_type in ("full", "delta") else "full"
            if req.db_path:
                db_path = req.db_path
            config = {
                "refresh": {
                    "type": refresh_type,
                    "delta_type": req.delta_type,
                },
                "processor": {"log_level": req.log_level},
            }
            # Pass --config with a YAML to suppress auto-discovery of local config.
            tmp_path = _write_temp_yaml(config)
            argv = [
                "--type", refresh_type,
                "--db", db_path,
                "--config", tmp_path,
                "--log-level", req.log_level,
            ]
            if req.delta_type and req.delta_type != "24h":
                argv.extend(["--delta-type", req.delta_type])
            if req.skip_isin_map:
                argv.append("--skip-isin-map")

        elif isinstance(req, GleifCheckRequest):
            config = {
                "check": {
                    "mode": req.mode,
                    "lei": req.lei,
                    "name": req.name,
                    "input_file": req.input_file,
                    "output_file": req.output_file,
                },
                "processor": {"log_level": req.log_level},
            }
            tmp_path = _write_temp_yaml(config)
            argv = ["--db", db_path, "--config", tmp_path, "--log-level", req.log_level]
            if req.lei:
                argv.extend(["--lei", req.lei])
            if req.name:
                argv.extend(["--name", req.name])
            if req.name and req.limit:
                argv.extend(["--limit", str(req.limit)])
            if req.input_file:
                argv.extend(["--input", req.input_file])
            if req.output_file:
                argv.extend(["--output", req.output_file])

        else:  # GleifBackfillRequest
            if req.db_path:
                db_path = req.db_path
            config = {
                "backfill": {
                    "input_file": req.input_file,
                    "output_file": req.output_file,
                    "format": req.format,
                },
                "processor": {"log_level": req.log_level},
            }
            tmp_path = _write_temp_yaml(config)
            argv = [
                "--input", req.input_file,
                "--output", req.output_file,
                "--db", db_path,
                "--config", tmp_path,
                "--log-level", req.log_level,
            ]
            if req.format != "auto":
                argv.extend(["--format", req.format])
            if req.skip_refresh:
                argv.append("--skip-refresh")

        logger.debug("Built GLEIF argv %s for script %s.", argv, script_name)
        return module_path, argv, config

    def build_utilities_argv(
        self,
        req: Union[XlsxConverterRequest, XmlConverterRequest],
        script_name: str,
    ) -> tuple[str, list[str], dict]:
        """Build argv for a file conversion utility script.

        Args:
            req: Validated utilities request schema.
            script_name: Registered script identifier, e.g. ``"xlsx_csv_converter"``.

        Returns:
            A tuple of ``(module_path, argv, config_snapshot)``.

        Raises:
            HTTPException: 400 if ``script_name`` is not a registered utility script.
        """
        module_path = _resolve_module(script_name)

        config: dict

        if isinstance(req, XlsxConverterRequest):
            config = {
                "conversion": {
                    "mode": req.mode,
                    "parent_dir": req.parent_dir,
                    "input_dir": req.input_dir,
                    "output_dir": req.output_dir,
                    "filter_year": req.filter_year,
                    "filter_quarter": req.filter_quarter,
                    "filter_phase": req.filter_phase,
                },
                "processor": {"log_level": req.log_level},
            }
            tmp_path = _write_temp_yaml(config)
            argv = ["--config", tmp_path, "--log-level", req.log_level]
            if req.filter_year:
                argv.extend(["--filter-year", req.filter_year])
            if req.filter_quarter:
                argv.extend(["--filter-quarter", req.filter_quarter])
            if req.filter_phase:
                argv.extend(["--filter-phase"] + req.filter_phase)
            if req.dry_run:
                argv.append("--dry-run")
            if req.force:
                argv.append("--force")

        else:  # XmlConverterRequest
            config = {
                "paths": {
                    "input_file": req.input_file,
                    "output_file": req.output_file,
                },
                "processor": {"log_level": req.log_level},
            }
            # xml_csv_converter uses CLI-only args, not --config
            argv = ["--input", req.input_file, "--log-level", req.log_level]
            if req.output_file:
                argv.extend(["--output-dir", req.output_file])

        logger.debug(
            "Built utilities argv %s for script %s.", argv, script_name
        )
        return module_path, argv, config


#: Module-level singleton for use in routers via direct import.
script_runner_service = ScriptRunnerService()

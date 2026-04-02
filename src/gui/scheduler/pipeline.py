#!/usr/bin/env python3
"""
PipelineExecutor
================

Executes a full scheduled pipeline by running each configured step
sequentially via subprocess, mirroring the ValidationOrchestrator pattern
from ``src.accuracy_testing.scripts.run_all_validations``.

Steps run in pipeline order: EXTRACT → COLLATE → VALIDATE → PUSH.
Only the steps present in ``ScheduleConfig.pipeline_steps`` are executed.
If any step fails the pipeline halts immediately and returns a FAILED record.

EXTRACT, COLLATE, and PUSH are stub implementations in Phase 1.
VALIDATE runs each configured validation script via subprocess.

Version 1.0 Changes:
- Initial implementation for Phase 1 scheduler foundation
- EXTRACT, COLLATE, PUSH are stubs pending Phase 4 implementation
"""

from __future__ import annotations

import logging
import subprocess
import sys
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from .file_naming import AutoFileNamer
from .models import (
    PipelineStep,
    RunRecord,
    RunStatus,
    ScheduleConfig,
    StepResult,
)

logger = logging.getLogger(__name__)

# Resolve project root once at import time so subprocess cwd is consistent.
_PROJECT_ROOT = Path(__file__).parent.parent.parent.parent


class PipelineExecutor:
    """Executes a full pipeline for a scheduled run.

    Each pipeline step is run synchronously in the calling thread.  The
    :class:`~src.gui.scheduler.engine.ScheduleEngine` is responsible for
    invoking this class inside a background :class:`~PySide6.QtCore.QThread`
    so the Qt event loop is not blocked.

    Example:
        >>> executor = PipelineExecutor()
        >>> record = executor.execute(config)
        >>> print(record.status)
        RunStatus.SUCCESS
    """

    STEP_TIMEOUT: int = 600  # seconds per subprocess call

    def execute(self, config: ScheduleConfig) -> RunRecord:
        """Execute all configured pipeline steps and return a completed RunRecord.

        Steps are executed in :class:`~.models.PipelineStep` declaration order
        (EXTRACT → COLLATE → VALIDATE → PUSH).  Only steps listed in
        ``config.pipeline_steps`` are run.  Execution halts on the first
        failed step.

        Args:
            config: Schedule configuration describing which steps and
                validation types to run.

        Returns:
            A :class:`~.models.RunRecord` describing the outcome of every
            executed step.
        """
        run_id = str(uuid.uuid4())
        timestamp = datetime.now()

        record = RunRecord(
            run_id=run_id,
            schedule_id=config.schedule_id,
            schedule_name=config.name,
            started_at=timestamp,
            status=RunStatus.RUNNING,
        )

        logger.info(
            "Pipeline starting: %s (run=%s, steps=%s)",
            config.name,
            run_id,
            [s.value for s in config.pipeline_steps],
        )

        for step in config.pipeline_steps:
            step_result = self._run_step(step, config, timestamp)
            record.step_results.append(step_result)

            if step_result.status == RunStatus.FAILED:
                record.status = RunStatus.FAILED
                record.error_message = step_result.error_message
                record.completed_at = datetime.now()
                logger.error(
                    "Pipeline failed at step %s: %s",
                    step.value,
                    step_result.error_message,
                )
                return record

        record.status = RunStatus.SUCCESS
        record.completed_at = datetime.now()
        record.output_files = [
            f for sr in record.step_results for f in sr.output_files
        ]

        logger.info(
            "Pipeline completed: %s (run=%s, outputs=%d)",
            config.name,
            run_id,
            len(record.output_files),
        )
        return record

    # ------------------------------------------------------------------
    # Step dispatch
    # ------------------------------------------------------------------

    def _run_step(
        self,
        step: PipelineStep,
        config: ScheduleConfig,
        timestamp: datetime,
    ) -> StepResult:
        """Dispatch to the appropriate step implementation.

        Args:
            step: Pipeline step to execute.
            config: Parent schedule configuration.
            timestamp: Run-start timestamp for deterministic file naming.

        Returns:
            :class:`~.models.StepResult` for the executed step.
        """
        dispatch = {
            PipelineStep.EXTRACT: self._run_extract_step,
            PipelineStep.COLLATE: self._run_collate_step,
            PipelineStep.VALIDATE: self._run_validate_step,
            PipelineStep.PUSH: self._run_push_step,
        }
        handler = dispatch[step]
        return handler(config, timestamp)

    # ------------------------------------------------------------------
    # Validate step (active implementation)
    # ------------------------------------------------------------------

    def _run_validate_step(
        self, config: ScheduleConfig, timestamp: datetime
    ) -> StepResult:
        """Run all configured validation scripts via subprocess.

        Iterates over ``config.validation_types``, executes each script
        module via ``sys.executable -m <module>``, and aggregates stdout and
        stderr.  Execution halts on the first non-zero return code.

        Args:
            config: Schedule configuration.
            timestamp: Run-start timestamp for deterministic file naming.

        Returns:
            :class:`~.models.StepResult` with aggregated output from all
            validation subprocesses.
        """
        step_result = StepResult(
            step=PipelineStep.VALIDATE,
            status=RunStatus.RUNNING,
            started_at=datetime.now(),
        )

        all_stdout: list[str] = []
        all_stderr: list[str] = []

        if not config.validation_types:
            step_result.status = RunStatus.SUCCESS
            step_result.completed_at = datetime.now()
            step_result.stdout = "No validation types configured — skipped."
            return step_result

        for vtype in config.validation_types:
            cmd = [sys.executable, "-m", vtype.script_module]

            logger.info(
                "Running %s: %s",
                vtype.display_name,
                " ".join(cmd),
            )

            try:
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=self.STEP_TIMEOUT,
                    cwd=str(_PROJECT_ROOT),
                )
            except subprocess.TimeoutExpired:
                step_result.status = RunStatus.FAILED
                step_result.error_message = (
                    f"{vtype.display_name} timed out after {self.STEP_TIMEOUT}s"
                )
                step_result.stdout = "\n".join(all_stdout)
                step_result.stderr = "\n".join(filter(None, all_stderr))
                step_result.completed_at = datetime.now()
                return step_result
            except Exception as exc:  # noqa: BLE001
                step_result.status = RunStatus.FAILED
                step_result.error_message = (
                    f"{vtype.display_name} subprocess error: {exc}"
                )
                step_result.stdout = "\n".join(all_stdout)
                step_result.stderr = "\n".join(filter(None, all_stderr))
                step_result.completed_at = datetime.now()
                return step_result

            header = f"=== {vtype.display_name} ==="
            all_stdout.append(f"{header}\n{result.stdout}")
            if result.stderr:
                all_stderr.append(f"{header}\n{result.stderr}")

            if result.returncode != 0:
                step_result.status = RunStatus.FAILED
                step_result.error_message = (
                    f"{vtype.display_name} exited with code {result.returncode}"
                )
                step_result.stdout = "\n".join(all_stdout)
                step_result.stderr = "\n".join(filter(None, all_stderr))
                step_result.completed_at = datetime.now()
                return step_result

            # Record output file if a destination was configured.
            if config.output_directory:
                output_path = AutoFileNamer.generate_output_path(
                    vtype,
                    config.schedule_period,
                    config.output_directory,
                    timestamp,
                )
                step_result.output_files.append(str(output_path))

        step_result.status = RunStatus.SUCCESS
        step_result.completed_at = datetime.now()
        step_result.stdout = "\n".join(all_stdout)
        step_result.stderr = "\n".join(filter(None, all_stderr))
        return step_result

    # ------------------------------------------------------------------
    # Stub steps (Phase 4)
    # ------------------------------------------------------------------

    def _run_extract_step(
        self, config: ScheduleConfig, timestamp: datetime
    ) -> StepResult:
        """Placeholder for the SQL extract step (Phase 4).

        Args:
            config: Schedule configuration.
            timestamp: Run-start timestamp.

        Returns:
            A successful :class:`~.models.StepResult` with a stub message.
        """
        logger.info(
            "Extract step not yet implemented for schedule %s — skipping.",
            config.schedule_id,
        )
        return StepResult(
            step=PipelineStep.EXTRACT,
            status=RunStatus.SUCCESS,
            started_at=datetime.now(),
            completed_at=datetime.now(),
            stdout="Extract step not yet implemented — skipped.",
        )

    def _run_collate_step(
        self, config: ScheduleConfig, timestamp: datetime
    ) -> StepResult:
        """Placeholder for the collation step (Phase 4).

        Args:
            config: Schedule configuration.
            timestamp: Run-start timestamp.

        Returns:
            A successful :class:`~.models.StepResult` with a stub message.
        """
        logger.info(
            "Collate step not yet implemented for schedule %s — skipping.",
            config.schedule_id,
        )
        return StepResult(
            step=PipelineStep.COLLATE,
            status=RunStatus.SUCCESS,
            started_at=datetime.now(),
            completed_at=datetime.now(),
            stdout="Collate step not yet implemented — skipped.",
        )

    def _run_push_step(
        self, config: ScheduleConfig, timestamp: datetime
    ) -> StepResult:
        """Placeholder for the data-push step (Phase 4).

        Args:
            config: Schedule configuration.
            timestamp: Run-start timestamp.

        Returns:
            A successful :class:`~.models.StepResult` with a stub message.
        """
        logger.info(
            "Push step not yet implemented for schedule %s — skipping.",
            config.schedule_id,
        )
        return StepResult(
            step=PipelineStep.PUSH,
            status=RunStatus.SUCCESS,
            started_at=datetime.now(),
            completed_at=datetime.now(),
            stdout="Push step not yet implemented — skipped.",
        )

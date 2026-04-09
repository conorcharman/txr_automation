"""
Tests for PipelineExecutor (src.gui.scheduler.pipeline) — Phase 2.

All subprocess calls are mocked so no external scripts are invoked.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.gui.scheduler.models import (
    PeriodType,
    PipelineStep,
    RunRecord,
    RunStatus,
    ScheduleConfig,
    ScheduleFrequency,
    SchedulePeriod,
    ValidationType,
)
from src.gui.scheduler.pipeline import PipelineExecutor


# ---------------------------------------------------------------------------
# Subprocess target used by _run_validate_step
# ---------------------------------------------------------------------------

_SUBPROCESS_RUN = "src.gui.scheduler.pipeline.subprocess.run"
_DTF_GENERATE = "src.accuracy_testing.core.dtf_runner.DTFRunner.generate_dtf_from_template"
_DTF_EXECUTE = "src.accuracy_testing.core.dtf_runner.DTFRunner.execute_dtf"
_DTF_WAIT = "src.accuracy_testing.core.dtf_runner.DTFRunner.wait_for_output"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_config(
    steps: list[PipelineStep] | None = None,
    validation_types: list[ValidationType] | None = None,
    output_directory: str = "",
) -> ScheduleConfig:
    """Return a minimal ScheduleConfig for pipeline tests.

    Args:
        steps: Pipeline steps to include. Defaults to ``[PipelineStep.VALIDATE]``.
        validation_types: Validation types. Defaults to ``[ValidationType.BUYER_ID]``.
        output_directory: Optional output directory path.

    Returns:
        Configured :class:`ScheduleConfig` instance.
    """
    return ScheduleConfig(
        schedule_id=str(uuid.uuid4()),
        name="Test Pipeline",
        enabled=True,
        frequency=ScheduleFrequency.DAILY,
        validation_types=validation_types or [ValidationType.BUYER_ID],
        pipeline_steps=steps or [PipelineStep.VALIDATE],
        schedule_period=SchedulePeriod(
            period_type=PeriodType.FISCAL_QUARTER,
            fiscal_year="FY26",
            quarter="Q1",
        ),
        output_directory=output_directory,
    )


def _mock_subprocess_result(returncode: int = 0) -> MagicMock:
    """Return a mock CompletedProcess with the given return code.

    Args:
        returncode: Process exit code to simulate.

    Returns:
        :class:`MagicMock` mimicking ``subprocess.CompletedProcess``.
    """
    result = MagicMock()
    result.returncode = returncode
    result.stdout = "Validation complete\n"
    result.stderr = ""
    return result


# ---------------------------------------------------------------------------
# VALIDATE step
# ---------------------------------------------------------------------------

class TestValidateStep:
    """Tests for the VALIDATE pipeline step (active subprocess-based implementation)."""

    def test_execute_validate_only_success(self) -> None:
        """A validate-only pipeline should return SUCCESS when subprocess exits 0."""
        config = _make_config(steps=[PipelineStep.VALIDATE])
        with patch(_SUBPROCESS_RUN, return_value=_mock_subprocess_result(0)):
            record = PipelineExecutor().execute(config)

        assert record.status == RunStatus.SUCCESS
        assert record.completed_at is not None

    def test_execute_validate_failure_halts_pipeline(self) -> None:
        """A non-zero subprocess exit code should mark the pipeline as FAILED with an error message."""
        config = _make_config(steps=[PipelineStep.VALIDATE])
        with patch(_SUBPROCESS_RUN, return_value=_mock_subprocess_result(1)):
            record = PipelineExecutor().execute(config)

        assert record.status == RunStatus.FAILED
        assert record.error_message, "error_message should be non-empty on failure"

    def test_run_record_has_timestamps(self) -> None:
        """Both started_at and completed_at should be populated after execute()."""
        config = _make_config(steps=[PipelineStep.VALIDATE])
        with patch(_SUBPROCESS_RUN, return_value=_mock_subprocess_result(0)):
            record = PipelineExecutor().execute(config)

        assert isinstance(record.started_at, datetime)
        assert isinstance(record.completed_at, datetime)

    def test_run_record_output_files_collected(self, tmp_path: Path) -> None:
        """Successful validate step should populate output_files when output_directory is set."""
        config = _make_config(
            steps=[PipelineStep.VALIDATE],
            output_directory=str(tmp_path),
        )
        with patch(_SUBPROCESS_RUN, return_value=_mock_subprocess_result(0)):
            record = PipelineExecutor().execute(config)

        assert record.status == RunStatus.SUCCESS
        assert len(record.output_files) > 0, "output_files should be populated"
        # Each entry should be a string path.
        for f in record.output_files:
            assert isinstance(f, str)


# ---------------------------------------------------------------------------
# Stub steps (EXTRACT, COLLATE, PUSH)
# ---------------------------------------------------------------------------

class TestStubSteps:
    """Tests for non-validate pipeline steps."""

    def test_execute_extract_step_is_stub_success(self) -> None:
        """An extract-only pipeline should return SUCCESS when DTFRunner succeeds."""
        config = _make_config(steps=[PipelineStep.EXTRACT])
        from pathlib import Path
        with patch(_DTF_GENERATE, return_value=Path("fake.dtf")), \
             patch(_DTF_EXECUTE, return_value=True), \
             patch(_DTF_WAIT, return_value=True):
            record = PipelineExecutor().execute(config)
        assert record.status == RunStatus.SUCCESS

    def test_execute_collate_step_is_stub_success(self) -> None:
        """A collate-only pipeline should return SUCCESS (stub implementation)."""
        config = _make_config(steps=[PipelineStep.COLLATE])
        record = PipelineExecutor().execute(config)
        assert record.status == RunStatus.SUCCESS

    def test_execute_push_step_is_stub_success(self) -> None:
        """A push-only pipeline should return SUCCESS (stub implementation)."""
        config = _make_config(steps=[PipelineStep.PUSH])
        record = PipelineExecutor().execute(config)
        assert record.status == RunStatus.SUCCESS


# ---------------------------------------------------------------------------
# All-steps ordering
# ---------------------------------------------------------------------------

class TestAllStepsInOrder:
    """Tests for pipeline step ordering when all four steps are configured."""

    def test_execute_all_steps_in_order(self) -> None:
        """step_results should contain 4 entries in EXTRACT→COLLATE→VALIDATE→PUSH order."""
        config = _make_config(
            steps=[
                PipelineStep.EXTRACT,
                PipelineStep.COLLATE,
                PipelineStep.VALIDATE,
                PipelineStep.PUSH,
            ],
        )
        from pathlib import Path
        with patch(_SUBPROCESS_RUN, return_value=_mock_subprocess_result(0)), \
             patch(_DTF_GENERATE, return_value=Path("fake.dtf")), \
             patch(_DTF_EXECUTE, return_value=True), \
             patch(_DTF_WAIT, return_value=True):
            record = PipelineExecutor().execute(config)

        assert record.status == RunStatus.SUCCESS
        assert len(record.step_results) == 4
        assert record.step_results[0].step == PipelineStep.EXTRACT
        assert record.step_results[1].step == PipelineStep.COLLATE
        assert record.step_results[2].step == PipelineStep.VALIDATE
        assert record.step_results[3].step == PipelineStep.PUSH

"""
Tests for the Power Automate automation CLI (src.automation.cli).

All external dependencies (QSettings-backed ScheduleStore, PipelineExecutor)
are mocked so no Qt display or subprocesses are required.
"""

from __future__ import annotations

import argparse
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Optional
from unittest.mock import MagicMock, patch

import pytest

from src.automation.cli import cmd_list_schedules, cmd_trigger_schedule
from src.gui.scheduler.models import (
    PipelineStep,
    RunRecord,
    RunStatus,
    ScheduleConfig,
    ScheduleFrequency,
    SchedulePeriod,
    ValidationType,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_config(
    schedule_id: str = "bbbbbbbb-0000-0000-0000-000000000002",
    name: str = "Test Schedule",
    output_dir: str = "",
) -> ScheduleConfig:
    """Return a minimal ScheduleConfig with predictable values."""
    return ScheduleConfig(
        schedule_id=schedule_id,
        name=name,
        enabled=True,
        frequency=ScheduleFrequency.DAILY,
        validation_types=[ValidationType.BUYER_ID],
        pipeline_steps=[PipelineStep.VALIDATE],
        schedule_period=SchedulePeriod(fiscal_year="FY26", quarter="Q1"),
        output_directory=output_dir,
    )


def _make_run_record(config: ScheduleConfig, run_id: Optional[str] = None) -> RunRecord:
    """Return a successful RunRecord for the given config."""
    ts = datetime(2026, 4, 1, 9, 0, 0)
    return RunRecord(
        run_id=run_id or str(uuid.uuid4()),
        schedule_id=config.schedule_id,
        schedule_name=config.name,
        started_at=ts,
        completed_at=ts,
        status=RunStatus.SUCCESS,
    )


# ---------------------------------------------------------------------------
# cmd_list_schedules
# ---------------------------------------------------------------------------

class TestCmdListSchedules:
    """Tests for the list-schedules CLI command."""

    def test_list_schedules_empty_returns_empty_json(self, capsys: pytest.CaptureFixture) -> None:
        """When the store is empty, cmd_list_schedules should print '[]' and return 0.

        Args:
            capsys: pytest fixture for capturing stdout/stderr.
        """
        mock_store = MagicMock()
        mock_store.list_schedules.return_value = []

        with patch("src.automation.cli.ScheduleStore", return_value=mock_store):
            result = cmd_list_schedules(argparse.Namespace())

        captured = capsys.readouterr()
        assert result == 0
        parsed = json.loads(captured.out)
        assert parsed == []

    def test_list_schedules_with_schedule_returns_json_list(
        self, capsys: pytest.CaptureFixture
    ) -> None:
        """When one schedule exists, the output should be a JSON list of length 1 with correct IDs.

        Args:
            capsys: pytest fixture for capturing stdout/stderr.
        """
        config = _make_config(schedule_id="cccccccc-0000-0000-0000-000000000003")
        mock_store = MagicMock()
        mock_store.list_schedules.return_value = [config]

        with patch("src.automation.cli.ScheduleStore", return_value=mock_store):
            result = cmd_list_schedules(argparse.Namespace())

        captured = capsys.readouterr()
        assert result == 0
        entries = json.loads(captured.out)
        assert len(entries) == 1
        assert entries[0]["schedule_id"] == "cccccccc-0000-0000-0000-000000000003"
        assert entries[0]["name"] == "Test Schedule"


# ---------------------------------------------------------------------------
# cmd_trigger_schedule
# ---------------------------------------------------------------------------

class TestCmdTriggerSchedule:
    """Tests for the trigger-schedule CLI command."""

    def test_trigger_schedule_not_found_returns_error_json(
        self, capsys: pytest.CaptureFixture
    ) -> None:
        """When the schedule is not found, the command should return 1 and print an error JSON.

        Args:
            capsys: pytest fixture for capturing stdout/stderr.
        """
        mock_store = MagicMock()
        mock_store.load_schedule.return_value = None

        with patch("src.automation.cli.ScheduleStore", return_value=mock_store):
            args = argparse.Namespace(schedule_id="nonexistent-uuid")
            result = cmd_trigger_schedule(args)

        captured = capsys.readouterr()
        assert result == 1
        payload = json.loads(captured.out)
        assert "error" in payload

    def test_trigger_schedule_calls_executor_and_writes_status_file(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        """A successful trigger should write _run_status.json containing the run_id.

        Args:
            tmp_path: pytest fixture providing a temporary directory.
            capsys: pytest fixture for capturing stdout/stderr.
        """
        run_id = "dddddddd-0000-0000-0000-000000000004"
        config = _make_config(
            schedule_id="eeeeeeee-0000-0000-0000-000000000005",
            output_dir=str(tmp_path),
        )
        mock_record = _make_run_record(config, run_id=run_id)

        mock_store = MagicMock()
        mock_store.load_schedule.return_value = config

        with (
            patch("src.automation.cli.ScheduleStore", return_value=mock_store),
            patch("src.automation.cli.PipelineExecutor") as mock_executor_cls,
        ):
            mock_executor_cls.return_value.execute.return_value = mock_record
            args = argparse.Namespace(schedule_id=config.schedule_id)
            result = cmd_trigger_schedule(args)

        assert result == 0

        status_file = tmp_path / "_run_status.json"
        assert status_file.exists(), "_run_status.json was not written to output_dir"
        status = json.loads(status_file.read_text(encoding="utf-8"))
        assert status["run_id"] == run_id
        assert status["status"] == "success"

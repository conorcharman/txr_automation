"""
Tests for scheduler models — enums, dataclasses, serialisation round-trips.
"""

from __future__ import annotations

from datetime import datetime

import pytest

from src.gui.scheduler.models import (
    PIPELINE_PRESETS,
    PeriodType,
    PipelinePreset,
    PipelineStep,
    RunRecord,
    RunStatus,
    ScheduleConfig,
    ScheduleFrequency,
    SchedulePeriod,
    StepResult,
    TestingPeriod as SchedulerTestingPeriod,
    ValidationType,
)


# ---------------------------------------------------------------------------
# ValidationType
# ---------------------------------------------------------------------------

class TestValidationType:
    def test_all_values_have_script_module(self) -> None:
        """Every ValidationType value must resolve to a non-empty script module."""
        for vtype in ValidationType:
            module = vtype.script_module
            assert module, f"{vtype.name} has empty script_module"
            assert "." in module, f"{vtype.name} script_module has no dots: {module!r}"

    def test_all_values_have_display_name(self) -> None:
        """Every ValidationType value must have a non-empty display name."""
        for vtype in ValidationType:
            name = vtype.display_name
            assert name, f"{vtype.name} has empty display_name"

    def test_buyer_id_display_name(self) -> None:
        assert ValidationType.BUYER_ID.display_name == "Buyer ID Validation"

    def test_seller_id_display_name(self) -> None:
        assert ValidationType.SELLER_ID.display_name == "Seller ID Validation"

    def test_inconsistent_buyer_display_name(self) -> None:
        assert (
            ValidationType.INCONSISTENT_BUYER_ID.display_name
            == "Inconsistent Buyer ID Validation"
        )

    def test_fund_trade_buyer_dm_display_name(self) -> None:
        assert "Fund Trade" in ValidationType.FUND_TRADE_BUYER_DM.display_name

    def test_script_module_buyer(self) -> None:
        assert (
            ValidationType.BUYER_ID.script_module
            == "accuracy_testing.scripts.buyer_id_validation"
        )

    def test_script_module_ftbdm(self) -> None:
        assert "ftbdm" in ValidationType.FUND_TRADE_BUYER_DM.script_module

    def test_enum_count(self) -> None:
        """Ensure all validation types are defined."""
        assert len(list(ValidationType)) == 10


# ---------------------------------------------------------------------------
# TestingPeriod
# ---------------------------------------------------------------------------

class TestTestingPeriod:
    def test_to_dict_round_trip(self) -> None:
        period = SchedulerTestingPeriod("FY26", "Q2")
        restored = SchedulerTestingPeriod.from_dict(period.to_dict())
        assert restored.fiscal_year == "FY26"
        assert restored.quarter == "Q2"

    def test_from_dict_defaults(self) -> None:
        """Missing keys should fall back to defaults without raising."""
        restored = SchedulerTestingPeriod.from_dict({})
        assert restored.fiscal_year == "FY26"
        assert restored.quarter == "Q1"

    def test_to_dict_keys(self) -> None:
        d = SchedulerTestingPeriod("FY25", "Q3").to_dict()
        assert set(d.keys()) == {"fiscal_year", "quarter"}


# ---------------------------------------------------------------------------
# ScheduleConfig
# ---------------------------------------------------------------------------

class TestScheduleConfig:
    def _make_config(self) -> ScheduleConfig:
        return ScheduleConfig(
            schedule_id="abc-123",
            name="Test Schedule",
            frequency=ScheduleFrequency.DAILY,
            validation_types=[ValidationType.BUYER_ID, ValidationType.SELLER_ID],
            pipeline_steps=[PipelineStep.VALIDATE],
            schedule_period=SchedulePeriod(
                period_type=PeriodType.FISCAL_QUARTER,
                fiscal_year="FY26",
                quarter="Q1",
            ),
            time_of_day="08:30",
        )

    def test_to_dict_contains_required_keys(self) -> None:
        d = self._make_config().to_dict()
        for key in (
            "schedule_id",
            "name",
            "enabled",
            "frequency",
            "validation_types",
            "pipeline_steps",
            "schedule_period",
        ):
            assert key in d, f"Missing key: {key}"

    def test_frequency_serialised_as_value(self) -> None:
        d = self._make_config().to_dict()
        assert d["frequency"] == "daily"

    def test_validation_types_serialised_as_values(self) -> None:
        d = self._make_config().to_dict()
        assert d["validation_types"] == ["buyer", "seller"]

    def test_pipeline_steps_serialised_as_values(self) -> None:
        d = self._make_config().to_dict()
        assert d["pipeline_steps"] == ["validate"]

    def test_round_trip(self) -> None:
        original = self._make_config()
        restored = ScheduleConfig.from_dict(original.to_dict())
        assert restored.schedule_id == original.schedule_id
        assert restored.name == original.name
        assert restored.frequency == original.frequency
        assert restored.validation_types == original.validation_types
        assert restored.pipeline_steps == original.pipeline_steps
        assert restored.schedule_period.fiscal_year == "FY26"
        assert restored.time_of_day == "08:30"

    def test_datetime_fields_round_trip(self) -> None:
        ts = datetime(2026, 4, 1, 9, 0, 0)
        config = self._make_config()
        config.created_at = ts
        config.last_run = ts
        config.next_run = ts
        restored = ScheduleConfig.from_dict(config.to_dict())
        assert restored.created_at == ts
        assert restored.last_run == ts
        assert restored.next_run == ts

    def test_none_datetime_fields(self) -> None:
        config = self._make_config()
        d = config.to_dict()
        assert d["created_at"] is None
        assert d["last_run"] is None
        assert d["next_run"] is None

    def test_default_pipeline_steps_all_steps(self) -> None:
        config = ScheduleConfig(schedule_id="x", name="y")
        assert config.pipeline_steps == list(PipelineStep)

    def test_missing_required_fields_raises(self) -> None:
        with pytest.raises(KeyError):
            ScheduleConfig.from_dict({"name": "no id"})


# ---------------------------------------------------------------------------
# StepResult
# ---------------------------------------------------------------------------

class TestStepResult:
    def test_round_trip(self) -> None:
        ts = datetime(2026, 4, 1, 9, 0, 0)
        result = StepResult(
            step=PipelineStep.VALIDATE,
            status=RunStatus.SUCCESS,
            started_at=ts,
            completed_at=ts,
            output_files=["output.csv"],
            stdout="done",
            stderr="",
            error_message="",
        )
        restored = StepResult.from_dict(result.to_dict())
        assert restored.step == PipelineStep.VALIDATE
        assert restored.status == RunStatus.SUCCESS
        assert restored.output_files == ["output.csv"]
        assert restored.started_at == ts

    def test_none_completed_at(self) -> None:
        result = StepResult(
            step=PipelineStep.EXTRACT,
            status=RunStatus.RUNNING,
            started_at=datetime.now(),
        )
        d = result.to_dict()
        assert d["completed_at"] is None
        restored = StepResult.from_dict(d)
        assert restored.completed_at is None


# ---------------------------------------------------------------------------
# RunRecord
# ---------------------------------------------------------------------------

class TestRunRecord:
    def _make_record(self) -> RunRecord:
        ts = datetime(2026, 4, 1, 9, 0, 0)
        return RunRecord(
            run_id="run-1",
            schedule_id="sched-1",
            schedule_name="Daily Buyer",
            started_at=ts,
            completed_at=ts,
            status=RunStatus.SUCCESS,
            output_files=["out.csv"],
            step_results=[
                StepResult(
                    step=PipelineStep.VALIDATE,
                    status=RunStatus.SUCCESS,
                    started_at=ts,
                    completed_at=ts,
                )
            ],
        )

    def test_round_trip(self) -> None:
        original = self._make_record()
        restored = RunRecord.from_dict(original.to_dict())
        assert restored.run_id == "run-1"
        assert restored.schedule_id == "sched-1"
        assert restored.status == RunStatus.SUCCESS
        assert len(restored.step_results) == 1
        assert restored.step_results[0].step == PipelineStep.VALIDATE

    def test_step_results_serialised(self) -> None:
        d = self._make_record().to_dict()
        assert isinstance(d["step_results"], list)
        assert d["step_results"][0]["step"] == "validate"

    def test_default_status_pending(self) -> None:
        record = RunRecord(
            run_id="r",
            schedule_id="s",
            schedule_name="N",
            started_at=datetime.now(),
        )
        assert record.status == RunStatus.PENDING


# ---------------------------------------------------------------------------
# PipelinePreset
# ---------------------------------------------------------------------------

class TestPipelinePresets:
    def test_presets_list_empty_in_v2(self) -> None:
        """Built-in presets were removed in scheduler v2.0."""
        assert PIPELINE_PRESETS == []

    def test_pipeline_preset_dataclass_still_constructible(self) -> None:
        """PipelinePreset remains available for backwards-compatible data models."""
        preset = PipelinePreset(
            key="legacy",
            display_name="Legacy",
            description="Legacy preset",
            validation_types=[ValidationType.BUYER_ID],
            pipeline_steps=[PipelineStep.VALIDATE],
        )
        assert preset.key == "legacy"
        assert preset.validation_types == [ValidationType.BUYER_ID]

# ---------------------------------------------------------------------------
# ScheduleFrequency and PipelineStep
# ---------------------------------------------------------------------------

class TestEnums:
    def test_schedule_frequency_values(self) -> None:
        expected = {"hourly", "daily", "weekly", "monthly", "quarterly", "custom"}
        assert {f.value for f in ScheduleFrequency} == expected

    def test_pipeline_step_order(self) -> None:
        steps = list(PipelineStep)
        assert steps.index(PipelineStep.EXTRACT) < steps.index(PipelineStep.COLLATE)
        assert steps.index(PipelineStep.COLLATE) < steps.index(PipelineStep.VALIDATE)
        assert steps.index(PipelineStep.VALIDATE) < steps.index(PipelineStep.PUSH)

    def test_run_status_values(self) -> None:
        expected = {"pending", "running", "success", "failed", "cancelled"}
        assert {s.value for s in RunStatus} == expected

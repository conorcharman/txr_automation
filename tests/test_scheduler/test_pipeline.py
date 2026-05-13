"""
Tests for legacy PipelineExecutor stub in scheduler v2.

Local subprocess-based execution was removed in favour of API-backed
pipeline triggering. These tests ensure the compatibility stub raises a
clear, stable error.
"""

from __future__ import annotations

import uuid

import pytest

from src.gui.scheduler.models import (
    PeriodType,
    PipelineStep,
    ScheduleConfig,
    ScheduleFrequency,
    SchedulePeriod,
    ValidationType,
)
from src.gui.scheduler.pipeline import PipelineExecutor


def _make_config(steps: list[PipelineStep] | None = None) -> ScheduleConfig:
    """Return a minimal schedule config for compatibility tests."""
    return ScheduleConfig(
        schedule_id=str(uuid.uuid4()),
        name="Test Pipeline",
        enabled=True,
        frequency=ScheduleFrequency.DAILY,
        validation_types=[ValidationType.BUYER_ID],
        pipeline_steps=steps or [PipelineStep.VALIDATE],
        schedule_period=SchedulePeriod(
            period_type=PeriodType.FISCAL_QUARTER,
            fiscal_year="FY26",
            quarter="Q1",
        ),
    )


class TestPipelineExecutorStub:
    """PipelineExecutor is retained as a compatibility stub only."""

    def test_execute_raises_not_implemented_for_validate(self) -> None:
        config = _make_config([PipelineStep.VALIDATE])
        with pytest.raises(NotImplementedError, match="Local pipeline execution has been removed"):
            PipelineExecutor().execute(config)

    def test_execute_raises_not_implemented_for_all_steps(self) -> None:
        config = _make_config(
            [
                PipelineStep.EXTRACT,
                PipelineStep.COLLATE,
                PipelineStep.VALIDATE,
                PipelineStep.PUSH,
            ]
        )
        with pytest.raises(NotImplementedError, match="Use the API backend"):
            PipelineExecutor().execute(config)

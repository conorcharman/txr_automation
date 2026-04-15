#!/usr/bin/env python3
"""
Scheduler Package
=================

TXR Automation scheduled pipeline infrastructure (API-backed).

Since version 2.0 all execution is delegated to the FastAPI backend.
The engine polls the API for status updates and emits Qt signals.

Public API
----------
- :class:`~.models.ScheduleConfig` — full schedule configuration
- :class:`~.models.ScheduleFrequency` — frequency enum (incl. QUARTERLY)
- :class:`~.models.PipelineStep` — legacy 4-step pipeline enum
- :class:`~.models.ValidationType` — validation type enum
- :class:`~.models.RunStatus` — run/step status enum
- :class:`~.models.RunRecord` — per-run result record
- :class:`~.models.StepResult` — per-step result record
- :class:`~.models.TestingPeriod` — fiscal year + quarter pair
- :class:`~.store.ScheduleStore` — QSettings-backed persistence
- :class:`~.engine.ScheduleEngine` — API-polling engine
- :class:`~.file_naming.AutoFileNamer` — deterministic output path generator
"""

from .engine import ScheduleEngine
from .file_naming import AutoFileNamer
from .models import (
    FREQUENCY_PERIOD_DEFAULTS,
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
    TestingPeriod,
    ValidationType,
)
from .pipeline import PipelineExecutor
from .store import ScheduleStore

__all__ = [
    "FREQUENCY_PERIOD_DEFAULTS",
    "PIPELINE_PRESETS",
    "AutoFileNamer",
    "PeriodType",
    "PipelineExecutor",
    "PipelinePreset",
    "PipelineStep",
    "RunRecord",
    "RunStatus",
    "ScheduleConfig",
    "ScheduleEngine",
    "ScheduleFrequency",
    "SchedulePeriod",
    "ScheduleStore",
    "StepResult",
    "TestingPeriod",
    "ValidationType",
]

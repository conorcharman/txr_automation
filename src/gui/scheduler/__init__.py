#!/usr/bin/env python3
"""
Scheduler Package
=================

TXR Automation scheduled pipeline infrastructure.

Provides enums, dataclasses, storage, file naming, pipeline execution,
and the timer-driven engine that ties everything together.

Public API
----------
- :class:`~.models.ScheduleConfig` — full schedule configuration
- :class:`~.models.ScheduleFrequency` — frequency enum
- :class:`~.models.PipelineStep` — pipeline step enum
- :class:`~.models.ValidationType` — validation type enum
- :class:`~.models.RunStatus` — run/step status enum
- :class:`~.models.RunRecord` — per-run result record
- :class:`~.models.StepResult` — per-step result record
- :class:`~.models.TestingPeriod` — fiscal year + quarter pair
- :class:`~.models.PipelinePreset` — named pipeline preset
- :data:`~.models.PIPELINE_PRESETS` — built-in preset list
- :class:`~.store.ScheduleStore` — QSettings-backed persistence
- :class:`~.engine.ScheduleEngine` — QTimer-driven execution engine
- :class:`~.file_naming.AutoFileNamer` — deterministic output path generator
- :class:`~.pipeline.PipelineExecutor` — subprocess-based step runner
"""

from .engine import ScheduleEngine
from .file_naming import AutoFileNamer
from .models import (
    PIPELINE_PRESETS,
    PipelinePreset,
    PipelineStep,
    RunRecord,
    RunStatus,
    ScheduleConfig,
    ScheduleFrequency,
    StepResult,
    TestingPeriod,
    ValidationType,
)
from .pipeline import PipelineExecutor
from .store import ScheduleStore

__all__ = [
    "PIPELINE_PRESETS",
    "AutoFileNamer",
    "PipelineExecutor",
    "PipelinePreset",
    "PipelineStep",
    "RunRecord",
    "RunStatus",
    "ScheduleConfig",
    "ScheduleEngine",
    "ScheduleFrequency",
    "ScheduleStore",
    "StepResult",
    "TestingPeriod",
    "ValidationType",
]

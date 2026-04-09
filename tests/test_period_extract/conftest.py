"""
Shared fixtures for test_period_extract package.

Provides a dict-backed QSettings stub (matching the one in test_scheduler)
and a minimal ScheduleConfig for use in CLI tests.
"""

from __future__ import annotations

import uuid
from typing import Any, Optional

import pytest

from src.gui.scheduler.models import (
    PipelineStep,
    ScheduleConfig,
    ScheduleFrequency,
    TestingPeriod,
    ValidationType,
)
from src.gui.scheduler.store import ScheduleStore


# ---------------------------------------------------------------------------
# Dict-backed QSettings stub
# ---------------------------------------------------------------------------

class _MockQSettings:
    """Lightweight stand-in for QSettings backed by a plain dict."""

    def __init__(self) -> None:
        self._data: dict[str, Any] = {}

    def value(self, key: str) -> Optional[Any]:
        return self._data.get(key)

    def setValue(self, key: str, value: Any) -> None:
        self._data[key] = value

    def remove(self, key: str) -> None:
        self._data.pop(key, None)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def mock_qsettings() -> _MockQSettings:
    """Return an isolated in-memory QSettings stub."""
    return _MockQSettings()


@pytest.fixture()
def store(mock_qsettings: _MockQSettings) -> ScheduleStore:
    """Return a ScheduleStore backed by the in-memory stub."""
    return ScheduleStore(qsettings=mock_qsettings)  # type: ignore[arg-type]


@pytest.fixture()
def sample_schedule_config() -> ScheduleConfig:
    """Return a minimal ScheduleConfig with known, stable values."""
    return ScheduleConfig(
        schedule_id="aaaaaaaa-0000-0000-0000-000000000001",
        name="Buyer ID Daily",
        enabled=True,
        frequency=ScheduleFrequency.DAILY,
        validation_types=[ValidationType.BUYER_ID],
        pipeline_steps=[PipelineStep.VALIDATE],
        testing_period=TestingPeriod("FY26", "Q1"),
    )

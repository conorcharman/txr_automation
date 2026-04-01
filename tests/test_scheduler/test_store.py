"""
Tests for ScheduleStore — QSettings-backed persistence.

Uses a mock QSettings backed by a plain dictionary to avoid any dependency
on the Windows registry or a running QApplication.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Any, Optional
from unittest.mock import MagicMock

import pytest

from src.gui.scheduler.models import (
    PipelineStep,
    RunRecord,
    RunStatus,
    ScheduleConfig,
    ScheduleFrequency,
    StepResult,
    TestingPeriod,
    ValidationType,
)
from src.gui.scheduler.store import ScheduleStore


# ---------------------------------------------------------------------------
# Minimal dict-backed QSettings stub
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
def store() -> ScheduleStore:
    """Return a ScheduleStore backed by an isolated in-memory QSettings stub."""
    return ScheduleStore(qsettings=_MockQSettings())  # type: ignore[arg-type]


def _make_config(name: str = "Test", schedule_id: Optional[str] = None) -> ScheduleConfig:
    return ScheduleConfig(
        schedule_id=schedule_id or str(uuid.uuid4()),
        name=name,
        frequency=ScheduleFrequency.DAILY,
        validation_types=[ValidationType.BUYER_ID],
        pipeline_steps=[PipelineStep.VALIDATE],
        testing_period=TestingPeriod("FY26", "Q1"),
    )


def _make_run_record(schedule_id: str, run_id: Optional[str] = None) -> RunRecord:
    ts = datetime(2026, 4, 1, 9, 0, 0)
    return RunRecord(
        run_id=run_id or str(uuid.uuid4()),
        schedule_id=schedule_id,
        schedule_name="Test",
        started_at=ts,
        completed_at=ts,
        status=RunStatus.SUCCESS,
    )


# ---------------------------------------------------------------------------
# Schedule CRUD
# ---------------------------------------------------------------------------

class TestScheduleStoreCRUD:
    def test_save_and_load_schedule(self, store: ScheduleStore) -> None:
        config = _make_config("Daily Buyer")
        store.save_schedule(config)
        loaded = store.load_schedule(config.schedule_id)
        assert loaded is not None
        assert loaded.name == "Daily Buyer"
        assert loaded.schedule_id == config.schedule_id

    def test_load_nonexistent_returns_none(self, store: ScheduleStore) -> None:
        assert store.load_schedule("nonexistent-id") is None

    def test_list_schedules_empty(self, store: ScheduleStore) -> None:
        assert store.list_schedules() == []

    def test_list_schedules_returns_all(self, store: ScheduleStore) -> None:
        configs = [_make_config(f"Sched {i}") for i in range(3)]
        for c in configs:
            store.save_schedule(c)
        result = store.list_schedules()
        assert len(result) == 3

    def test_list_schedules_insertion_order(self, store: ScheduleStore) -> None:
        configs = [_make_config(f"S{i}") for i in range(3)]
        for c in configs:
            store.save_schedule(c)
        names = [s.name for s in store.list_schedules()]
        assert names == ["S0", "S1", "S2"]

    def test_save_overwrites_existing(self, store: ScheduleStore) -> None:
        config = _make_config("Original")
        store.save_schedule(config)
        config.name = "Updated"
        store.save_schedule(config)
        loaded = store.load_schedule(config.schedule_id)
        assert loaded is not None
        assert loaded.name == "Updated"
        # Index should not grow on update.
        assert len(store.list_schedules()) == 1

    def test_delete_schedule(self, store: ScheduleStore) -> None:
        config = _make_config()
        store.save_schedule(config)
        store.delete_schedule(config.schedule_id)
        assert store.load_schedule(config.schedule_id) is None
        assert store.list_schedules() == []

    def test_delete_nonexistent_does_not_raise(self, store: ScheduleStore) -> None:
        store.delete_schedule("ghost-id")  # should not raise

    def test_update_last_run(self, store: ScheduleStore) -> None:
        config = _make_config()
        store.save_schedule(config)
        ts = datetime(2026, 4, 1, 10, 30, 0)
        store.update_last_run(config.schedule_id, ts)
        loaded = store.load_schedule(config.schedule_id)
        assert loaded is not None
        assert loaded.last_run == ts

    def test_update_next_run(self, store: ScheduleStore) -> None:
        config = _make_config()
        store.save_schedule(config)
        ts = datetime(2026, 4, 2, 9, 0, 0)
        store.update_next_run(config.schedule_id, ts)
        loaded = store.load_schedule(config.schedule_id)
        assert loaded is not None
        assert loaded.next_run == ts

    def test_update_next_run_to_none(self, store: ScheduleStore) -> None:
        config = _make_config()
        config.next_run = datetime(2026, 4, 2, 9, 0, 0)
        store.save_schedule(config)
        store.update_next_run(config.schedule_id, None)
        loaded = store.load_schedule(config.schedule_id)
        assert loaded is not None
        assert loaded.next_run is None

    def test_update_last_run_nonexistent_does_not_raise(
        self, store: ScheduleStore
    ) -> None:
        store.update_last_run("ghost", datetime.now())

    def test_roundtrip_validation_types(self, store: ScheduleStore) -> None:
        config = _make_config()
        config.validation_types = [
            ValidationType.BUYER_ID,
            ValidationType.INCONSISTENT_BUYER_ID,
        ]
        store.save_schedule(config)
        loaded = store.load_schedule(config.schedule_id)
        assert loaded is not None
        assert loaded.validation_types == config.validation_types


# ---------------------------------------------------------------------------
# Run history
# ---------------------------------------------------------------------------

class TestScheduleStoreHistory:
    def test_save_and_retrieve_run_record(self, store: ScheduleStore) -> None:
        config = _make_config()
        store.save_schedule(config)
        record = _make_run_record(config.schedule_id)
        store.save_run_record(record)
        history = store.get_run_history(config.schedule_id)
        assert len(history) == 1
        assert history[0].run_id == record.run_id

    def test_get_run_history_empty(self, store: ScheduleStore) -> None:
        assert store.get_run_history("no-such-schedule") == []

    def test_get_run_history_newest_first(self, store: ScheduleStore) -> None:
        config = _make_config()
        store.save_schedule(config)
        ts_base = datetime(2026, 4, 1, 9, 0, 0)
        records = []
        for i in range(3):
            r = _make_run_record(config.schedule_id)
            r.started_at = ts_base.replace(hour=i + 6)
            store.save_run_record(r)
            records.append(r)

        history = store.get_run_history(config.schedule_id)
        # Most recent first — last inserted has hour=8
        assert history[0].started_at.hour == 8

    def test_get_run_history_respects_limit(self, store: ScheduleStore) -> None:
        config = _make_config()
        store.save_schedule(config)
        for _ in range(10):
            store.save_run_record(_make_run_record(config.schedule_id))

        history = store.get_run_history(config.schedule_id, limit=5)
        assert len(history) <= 5

    def test_get_all_run_history(self, store: ScheduleStore) -> None:
        configs = [_make_config(f"S{i}") for i in range(2)]
        for c in configs:
            store.save_schedule(c)
            store.save_run_record(_make_run_record(c.schedule_id))

        all_history = store.get_all_run_history()
        assert len(all_history) == 2

    def test_trim_history_removes_oldest(self, store: ScheduleStore) -> None:
        config = _make_config()
        store.save_schedule(config)
        run_ids = []
        for i in range(5):
            r = _make_run_record(config.schedule_id)
            run_ids.append(r.run_id)
            store.save_run_record(r)

        store.trim_history(config.schedule_id, max_records=3)
        history = store.get_run_history(config.schedule_id)
        # After trimming to 3, we should have at most 3 records.
        assert len(history) <= 3

    def test_trim_history_no_op_when_under_limit(
        self, store: ScheduleStore
    ) -> None:
        config = _make_config()
        store.save_schedule(config)
        for _ in range(2):
            store.save_run_record(_make_run_record(config.schedule_id))

        store.trim_history(config.schedule_id, max_records=100)
        history = store.get_run_history(config.schedule_id)
        assert len(history) == 2

    def test_run_record_step_results_persist(self, store: ScheduleStore) -> None:
        config = _make_config()
        store.save_schedule(config)
        ts = datetime(2026, 4, 1, 9, 0, 0)
        record = _make_run_record(config.schedule_id)
        record.step_results = [
            StepResult(
                step=PipelineStep.VALIDATE,
                status=RunStatus.SUCCESS,
                started_at=ts,
                completed_at=ts,
            )
        ]
        store.save_run_record(record)
        history = store.get_run_history(config.schedule_id)
        assert len(history[0].step_results) == 1
        assert history[0].step_results[0].step == PipelineStep.VALIDATE

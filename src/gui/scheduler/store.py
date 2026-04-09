#!/usr/bin/env python3
"""
ScheduleStore
=============

Persistent storage for schedule configurations and run history via QSettings.

All data is stored in the Windows registry / AppData under the usual
``TXRAutomation / txr_automation`` application identifiers, using a
``scheduler/`` key prefix to avoid collisions with GUI settings.

Complex values (lists, dicts) are JSON-encoded before writing so that
QSettings serialises them as plain strings — mirroring the pattern used
by :class:`src.gui.utils.settings.SettingsManager`.

Version 1.0 Changes:
- Initial implementation for Phase 1 scheduler foundation
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Optional

from PySide6.QtCore import QSettings

from .models import RunRecord, ScheduleConfig

logger = logging.getLogger(__name__)


class ScheduleStore:
    """Persist and retrieve schedule configurations and run history.

    Uses QSettings for storage so data survives process restarts without
    requiring a database.  A separate index key tracks the list of known
    schedule IDs to allow fast enumeration without iterating all registry keys.

    Args:
        qsettings: Optional pre-constructed :class:`QSettings` instance,
            primarily used for unit-test injection.  When ``None`` a default
            instance is created using the standard application identifiers.

    Example:
        >>> store = ScheduleStore()
        >>> store.save_schedule(config)
        >>> schedules = store.list_schedules()
    """

    _SCHEDULE_IDS_KEY = "scheduler/schedule_ids"
    _SCHEDULE_KEY_PREFIX = "scheduler/schedules/"
    _HISTORY_KEY_PREFIX = "scheduler/history/"
    _SCHEDULE_HISTORY_PREFIX = "scheduler/schedule_history/"

    def __init__(self, qsettings: Optional[QSettings] = None) -> None:
        if qsettings is not None:
            self._settings = qsettings
        else:
            self._settings = QSettings("TXRAutomation", "txr_automation")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_json_list(self, key: str) -> list:
        """Load a JSON-encoded list from QSettings.

        Args:
            key: Settings key to read.

        Returns:
            Decoded list, or an empty list if the key is absent or malformed.
        """
        raw = self._settings.value(key)
        if raw is None:
            return []
        if isinstance(raw, list):
            return raw
        try:
            parsed = json.loads(raw)
            return parsed if isinstance(parsed, list) else []
        except (json.JSONDecodeError, TypeError):
            return []

    def _set_json_list(self, key: str, value: list) -> None:
        """Store a list as a JSON-encoded string in QSettings.

        Args:
            key: Settings key to write.
            value: List to serialise.
        """
        self._settings.setValue(key, json.dumps(value))

    def _get_json_str(self, key: str) -> Optional[str]:
        """Read a raw string value from QSettings.

        Args:
            key: Settings key to read.

        Returns:
            The stored string, or ``None`` if absent.
        """
        val = self._settings.value(key)
        return str(val) if val is not None else None

    # ------------------------------------------------------------------
    # Schedule CRUD
    # ------------------------------------------------------------------

    def save_schedule(self, config: ScheduleConfig) -> None:
        """Persist a schedule configuration.

        Creates the schedule if it does not exist, or updates it in place.
        The schedule index is updated atomically.

        Args:
            config: Schedule configuration to store.
        """
        key = f"{self._SCHEDULE_KEY_PREFIX}{config.schedule_id}"
        self._settings.setValue(key, json.dumps(config.to_dict()))

        ids = self._get_json_list(self._SCHEDULE_IDS_KEY)
        if config.schedule_id not in ids:
            ids.append(config.schedule_id)
            self._set_json_list(self._SCHEDULE_IDS_KEY, ids)

        logger.debug("Saved schedule %s (%s)", config.schedule_id, config.name)

    def load_schedule(self, schedule_id: str) -> Optional[ScheduleConfig]:
        """Load a single schedule configuration by ID.

        Args:
            schedule_id: UUID string identifying the schedule.

        Returns:
            :class:`ScheduleConfig` instance, or ``None`` if not found or
            if the stored data is malformed.
        """
        key = f"{self._SCHEDULE_KEY_PREFIX}{schedule_id}"
        raw = self._get_json_str(key)
        if raw is None:
            return None
        try:
            data = json.loads(raw)
            return ScheduleConfig.from_dict(data)
        except (json.JSONDecodeError, KeyError, ValueError) as exc:
            logger.warning(
                "Failed to deserialise schedule %s: %s", schedule_id, exc
            )
            return None

    def list_schedules(self) -> list[ScheduleConfig]:
        """Return all stored schedule configurations.

        Schedules that fail deserialisation are silently skipped.

        Returns:
            List of :class:`ScheduleConfig` instances, in insertion order.
        """
        ids = self._get_json_list(self._SCHEDULE_IDS_KEY)
        schedules: list[ScheduleConfig] = []
        for sid in ids:
            config = self.load_schedule(sid)
            if config is not None:
                schedules.append(config)
        return schedules

    def delete_schedule(self, schedule_id: str) -> None:
        """Remove a schedule and its history index entry.

        Does not delete individual run records — use :meth:`trim_history` to
        purge them separately if needed.

        Args:
            schedule_id: UUID string identifying the schedule to remove.
        """
        self._settings.remove(f"{self._SCHEDULE_KEY_PREFIX}{schedule_id}")
        ids = self._get_json_list(self._SCHEDULE_IDS_KEY)
        ids = [i for i in ids if i != schedule_id]
        self._set_json_list(self._SCHEDULE_IDS_KEY, ids)
        self._settings.remove(f"{self._SCHEDULE_HISTORY_PREFIX}{schedule_id}")

        logger.debug("Deleted schedule %s", schedule_id)

    def update_last_run(self, schedule_id: str, timestamp: datetime) -> None:
        """Update the ``last_run`` timestamp on a stored schedule.

        Args:
            schedule_id: UUID string identifying the schedule.
            timestamp: Datetime of the most recent run start.
        """
        config = self.load_schedule(schedule_id)
        if config is None:
            logger.warning(
                "update_last_run: schedule %s not found", schedule_id
            )
            return
        config.last_run = timestamp
        self.save_schedule(config)

    def update_next_run(
        self, schedule_id: str, timestamp: Optional[datetime]
    ) -> None:
        """Update the pre-calculated ``next_run`` timestamp on a stored schedule.

        Args:
            schedule_id: UUID string identifying the schedule.
            timestamp: Next scheduled run datetime, or ``None`` to clear it.
        """
        config = self.load_schedule(schedule_id)
        if config is None:
            logger.warning(
                "update_next_run: schedule %s not found", schedule_id
            )
            return
        config.next_run = timestamp
        self.save_schedule(config)

    # ------------------------------------------------------------------
    # Run history
    # ------------------------------------------------------------------

    def save_run_record(self, record: RunRecord) -> None:
        """Persist a completed run record and update the per-schedule history index.

        Automatically calls :meth:`trim_history` to cap the history at 100 entries.

        Args:
            record: Completed :class:`RunRecord` to store.
        """
        key = f"{self._HISTORY_KEY_PREFIX}{record.run_id}"
        self._settings.setValue(key, json.dumps(record.to_dict()))

        history_key = f"{self._SCHEDULE_HISTORY_PREFIX}{record.schedule_id}"
        run_ids = self._get_json_list(history_key)
        if record.run_id not in run_ids:
            run_ids.append(record.run_id)
            self._set_json_list(history_key, run_ids)

        self.trim_history(record.schedule_id)

        logger.debug(
            "Saved run record %s for schedule %s",
            record.run_id,
            record.schedule_id,
        )

    def get_run_history(
        self, schedule_id: str, limit: int = 50
    ) -> list[RunRecord]:
        """Return run history for a specific schedule, newest first.

        Args:
            schedule_id: UUID string identifying the schedule.
            limit: Maximum number of records to return.

        Returns:
            List of :class:`RunRecord` instances, most recent first.
        """
        history_key = f"{self._SCHEDULE_HISTORY_PREFIX}{schedule_id}"
        run_ids = self._get_json_list(history_key)
        run_ids = run_ids[-limit:]

        records: list[RunRecord] = []
        for run_id in reversed(run_ids):
            raw = self._get_json_str(f"{self._HISTORY_KEY_PREFIX}{run_id}")
            if raw is None:
                continue
            try:
                records.append(RunRecord.from_dict(json.loads(raw)))
            except (json.JSONDecodeError, KeyError, ValueError) as exc:
                logger.warning(
                    "Failed to deserialise run record %s: %s", run_id, exc
                )
        return records

    def get_all_run_history(self, limit: int = 100) -> list[RunRecord]:
        """Return run history across all schedules, newest first.

        Args:
            limit: Maximum number of records to return after combining and
                sorting all schedule histories.

        Returns:
            List of :class:`RunRecord` instances, most recent first.
        """
        ids = self._get_json_list(self._SCHEDULE_IDS_KEY)
        all_records: list[RunRecord] = []
        for sid in ids:
            all_records.extend(self.get_run_history(sid, limit=limit))

        all_records.sort(key=lambda r: r.started_at, reverse=True)
        return all_records[:limit]

    def trim_history(self, schedule_id: str, max_records: int = 100) -> None:
        """Remove the oldest run records for a schedule, keeping only the latest N.

        Args:
            schedule_id: UUID string identifying the schedule.
            max_records: Maximum number of run records to retain.
        """
        history_key = f"{self._SCHEDULE_HISTORY_PREFIX}{schedule_id}"
        run_ids = self._get_json_list(history_key)
        if len(run_ids) <= max_records:
            return

        to_remove = run_ids[:-max_records]
        for run_id in to_remove:
            self._settings.remove(f"{self._HISTORY_KEY_PREFIX}{run_id}")
            logger.debug(
                "Trimmed old run record %s from schedule %s",
                run_id,
                schedule_id,
            )

        run_ids = run_ids[-max_records:]
        self._set_json_list(history_key, run_ids)

#!/usr/bin/env python3
"""
ScheduleEngine
==============

QTimer-based engine that polls stored schedules every 30 seconds, enqueues
those that are due, and executes them sequentially — one pipeline at a time —
via a background :class:`PySide6.QtCore.QThread`.

The engine emits Qt signals so the GUI and system-tray service can react to
pipeline lifecycle events without polling.

Design notes:
- Pipelines run one at a time (``_running`` flag + ``_queue`` deque).
- A ``_queued_ids`` set prevents the same schedule being enqueued twice
  before it has had a chance to run.
- ``_calculate_next_run`` uses :mod:`croniter` for CUSTOM expressions and
  plain :mod:`datetime` arithmetic for the built-in frequencies.
- ``_execute_next`` creates a fresh ``_RunnerThread`` for each execution so
  that a previous thread's resources are fully released before the next run.

Version 1.0 Changes:
- Initial implementation for Phase 1 scheduler foundation
"""

from __future__ import annotations

import collections
import logging
from datetime import datetime, timedelta
from typing import Optional

from PySide6.QtCore import QObject, QThread, QTimer, Signal

from .models import RunRecord, RunStatus, ScheduleConfig, ScheduleFrequency
from .pipeline import PipelineExecutor
from .store import ScheduleStore

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Background runner thread
# ---------------------------------------------------------------------------

class _RunnerThread(QThread):
    """Executes a :class:`~.pipeline.PipelineExecutor` in a background thread.

    Args:
        config: Schedule configuration to execute.
        executor: Pre-constructed pipeline executor instance.
        parent: Optional parent :class:`~PySide6.QtCore.QObject`.
    """

    run_completed = Signal(object)  # emits RunRecord

    def __init__(
        self,
        config: ScheduleConfig,
        executor: PipelineExecutor,
        parent: Optional[QObject] = None,
    ) -> None:
        super().__init__(parent)
        self._config = config
        self._executor = executor

    def run(self) -> None:
        """Execute the pipeline and emit ``run_completed`` when done."""
        try:
            record = self._executor.execute(self._config)
        except Exception as exc:  # noqa: BLE001
            logger.exception(
                "Unhandled exception in runner thread for %s: %s",
                self._config.schedule_id,
                exc,
            )
            from .models import RunRecord, RunStatus  # noqa: PLC0415

            record = RunRecord(
                run_id="error",
                schedule_id=self._config.schedule_id,
                schedule_name=self._config.name,
                started_at=datetime.now(),
                completed_at=datetime.now(),
                status=RunStatus.FAILED,
                error_message=str(exc),
            )
        self.run_completed.emit(record)


# ---------------------------------------------------------------------------
# Schedule engine
# ---------------------------------------------------------------------------

class ScheduleEngine(QObject):
    """Drives the scheduled pipeline execution queue.

    Polls stored schedules every 30 seconds (configurable via ``poll_interval``).
    Schedules whose ``next_run`` is ``None`` or in the past are enqueued for
    immediate execution.

    Signals:
        pipeline_started (str, str): Emitted when a pipeline begins.
            Arguments: ``(schedule_id, schedule_name)``.
        pipeline_completed (str, str, bool): Emitted when a pipeline finishes.
            Arguments: ``(schedule_id, schedule_name, success)``.
        pipeline_failed (str, str, str): Emitted when a pipeline fails.
            Arguments: ``(schedule_id, schedule_name, error_message)``.
        schedule_updated (str): Emitted after ``next_run`` is recalculated.
            Argument: ``schedule_id``.

    Args:
        store: :class:`~.store.ScheduleStore` instance providing persistence.
        poll_interval: Timer interval in milliseconds (default 30 000).
        parent: Optional parent :class:`~PySide6.QtCore.QObject`.

    Example:
        >>> store = ScheduleStore()
        >>> engine = ScheduleEngine(store)
        >>> engine.pipeline_completed.connect(on_completed)
        >>> engine.start()
    """

    pipeline_started = Signal(str, str)          # schedule_id, schedule_name
    pipeline_completed = Signal(str, str, bool)  # schedule_id, schedule_name, success
    pipeline_failed = Signal(str, str, str)      # schedule_id, schedule_name, error_message
    schedule_updated = Signal(str)               # schedule_id

    def __init__(
        self,
        store: ScheduleStore,
        poll_interval: int = 30_000,
        parent: Optional[QObject] = None,
    ) -> None:
        super().__init__(parent)
        self._store = store
        self._queue: collections.deque[ScheduleConfig] = collections.deque()
        self._queued_ids: set[str] = set()
        self._running: bool = False
        self._current_run_id: Optional[str] = None
        self._runner_thread: Optional[_RunnerThread] = None

        self._timer = QTimer(self)
        self._timer.setInterval(poll_interval)
        self._timer.timeout.connect(self._tick)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Start the engine and begin polling for due schedules.

        Performs an immediate first check before the timer fires.
        """
        logger.info("ScheduleEngine starting (poll interval=%dms)", self._timer.interval())
        self._timer.start()
        self._tick()

    def stop(self) -> None:
        """Stop the engine.  In-progress pipelines are allowed to finish."""
        logger.info("ScheduleEngine stopping.")
        self._timer.stop()

    def trigger_now(self, schedule_id: str) -> bool:
        """Manually enqueue a schedule for immediate execution.

        If the schedule is already queued, the duplicate is silently ignored.

        Args:
            schedule_id: UUID string identifying the schedule to run.

        Returns:
            ``True`` if the schedule was found and enqueued (or was already
            queued), ``False`` if the schedule does not exist.
        """
        config = self._store.load_schedule(schedule_id)
        if config is None:
            logger.warning("trigger_now: schedule %s not found", schedule_id)
            return False

        if schedule_id not in self._queued_ids:
            self._queue.append(config)
            self._queued_ids.add(schedule_id)
            logger.info("Manually enqueued schedule %s (%s)", schedule_id, config.name)

        self._execute_next()
        return True

    # ------------------------------------------------------------------
    # Internal scheduling logic
    # ------------------------------------------------------------------

    def _tick(self) -> None:
        """Check all enabled schedules and enqueue any that are due."""
        schedules = self._store.list_schedules()
        enqueued = 0

        for config in schedules:
            if not config.enabled:
                continue
            if config.schedule_id in self._queued_ids:
                continue
            if self._is_due(config):
                self._queue.append(config)
                self._queued_ids.add(config.schedule_id)
                enqueued += 1
                logger.debug(
                    "Enqueued schedule %s (%s)", config.schedule_id, config.name
                )

        if enqueued:
            logger.info("Tick: enqueued %d schedule(s)", enqueued)

        self._execute_next()

    def _is_due(self, config: ScheduleConfig) -> bool:
        """Return ``True`` if the schedule's next run time is now or in the past.

        A schedule with ``next_run=None`` is treated as immediately due so
        that newly created schedules run on their first tick.

        Args:
            config: Schedule configuration to check.

        Returns:
            ``True`` if the schedule should be run now.
        """
        if config.next_run is None:
            return True
        return datetime.now() >= config.next_run

    def _calculate_next_run(self, config: ScheduleConfig) -> datetime:
        """Calculate the next run datetime for a schedule.

        Uses :mod:`croniter` for CUSTOM expressions and plain
        :class:`~datetime.datetime` arithmetic for the built-in frequencies.

        Args:
            config: Schedule configuration.

        Returns:
            Next scheduled run :class:`~datetime.datetime`.

        Raises:
            ValueError: If ``config.frequency`` is ``CUSTOM`` and
                ``config.cron_expression`` is empty or invalid.
        """
        now = datetime.now()

        if config.frequency == ScheduleFrequency.HOURLY:
            return now + timedelta(hours=1)

        if config.frequency == ScheduleFrequency.DAILY:
            return self._next_daily(config, now)

        if config.frequency == ScheduleFrequency.WEEKLY:
            return self._next_weekly(config, now)

        if config.frequency == ScheduleFrequency.MONTHLY:
            return self._next_monthly(config, now)

        if config.frequency == ScheduleFrequency.CUSTOM:
            return self._next_custom(config, now)

        # Fallback: 24 hours from now.
        return now + timedelta(hours=24)

    # ------------------------------------------------------------------
    # Frequency helpers
    # ------------------------------------------------------------------

    def _parse_time_of_day(self, time_str: str) -> tuple[int, int]:
        """Parse a ``HH:MM`` time string into (hour, minute).

        Args:
            time_str: Time string in ``HH:MM`` format.

        Returns:
            Tuple of (hour, minute) as integers.
        """
        parts = time_str.split(":")
        hour = int(parts[0]) if parts else 9
        minute = int(parts[1]) if len(parts) > 1 else 0
        return hour, minute

    def _next_daily(self, config: ScheduleConfig, now: datetime) -> datetime:
        """Return the next daily trigger time.

        Args:
            config: Schedule configuration.
            now: Current datetime.

        Returns:
            Tomorrow (or later today) at ``config.time_of_day``.
        """
        hour, minute = self._parse_time_of_day(config.time_of_day)
        candidate = now.replace(
            hour=hour, minute=minute, second=0, microsecond=0
        )
        if candidate <= now:
            candidate += timedelta(days=1)
        return candidate

    def _next_weekly(self, config: ScheduleConfig, now: datetime) -> datetime:
        """Return the next weekly trigger time on the configured day.

        Args:
            config: Schedule configuration (``day_of_week``: 0=Monday … 6=Sunday).
            now: Current datetime.

        Returns:
            Next occurrence of ``config.day_of_week`` at ``config.time_of_day``.
        """
        hour, minute = self._parse_time_of_day(config.time_of_day)
        days_ahead = config.day_of_week - now.weekday()

        if days_ahead < 0:
            days_ahead += 7
        elif days_ahead == 0:
            candidate = now.replace(
                hour=hour, minute=minute, second=0, microsecond=0
            )
            if candidate <= now:
                days_ahead = 7

        return (
            now.replace(hour=hour, minute=minute, second=0, microsecond=0)
            + timedelta(days=days_ahead)
        )

    def _next_monthly(self, config: ScheduleConfig, now: datetime) -> datetime:
        """Return the next monthly trigger time on the configured day.

        Supports days 1-28 to avoid month-length issues.

        Args:
            config: Schedule configuration (``day_of_month``: 1-28).
            now: Current datetime.

        Returns:
            Next occurrence of ``config.day_of_month`` at ``config.time_of_day``.
        """
        hour, minute = self._parse_time_of_day(config.time_of_day)
        try:
            candidate = now.replace(
                day=config.day_of_month,
                hour=hour,
                minute=minute,
                second=0,
                microsecond=0,
            )
        except ValueError:
            # day_of_month out of range for this month; fall back to day 1.
            candidate = now.replace(
                day=1, hour=hour, minute=minute, second=0, microsecond=0
            )

        if candidate <= now:
            # Advance to next month.
            if now.month == 12:
                candidate = candidate.replace(year=now.year + 1, month=1)
            else:
                try:
                    candidate = candidate.replace(month=now.month + 1)
                except ValueError:
                    candidate = candidate.replace(
                        month=now.month + 1, day=1
                    )
        return candidate

    def _next_custom(self, config: ScheduleConfig, now: datetime) -> datetime:
        """Return the next trigger time using a cron expression.

        Args:
            config: Schedule configuration with a valid ``cron_expression``.
            now: Current datetime.

        Returns:
            Next trigger datetime from :mod:`croniter`.

        Raises:
            ValueError: If the cron expression is empty or invalid.
        """
        if not config.cron_expression:
            raise ValueError(
                f"Schedule {config.schedule_id!r} has CUSTOM frequency but no "
                "cron_expression set."
            )
        try:
            from croniter import croniter  # noqa: PLC0415

            return croniter(config.cron_expression, now).get_next(datetime)
        except Exception as exc:
            raise ValueError(
                f"Invalid cron expression {config.cron_expression!r}: {exc}"
            ) from exc

    # ------------------------------------------------------------------
    # Pipeline execution
    # ------------------------------------------------------------------

    def _execute_next(self) -> None:
        """Execute the first queued schedule if the engine is idle.

        Does nothing if a pipeline is already running or the queue is empty.
        """
        if self._running or not self._queue:
            return

        config = self._queue.popleft()
        self._running = True

        logger.info(
            "Starting pipeline for schedule %s (%s)", config.schedule_id, config.name
        )
        self.pipeline_started.emit(config.schedule_id, config.name)

        executor = PipelineExecutor()
        runner = _RunnerThread(config, executor, self)
        runner.run_completed.connect(self._on_pipeline_completed)
        # Hold a reference so the thread is not garbage-collected.
        self._runner_thread = runner
        runner.start()

    def _on_pipeline_completed(self, record: RunRecord) -> None:
        """Handle pipeline completion: persist the record, update schedule, emit signals.

        Args:
            record: Completed :class:`~.models.RunRecord` returned by the runner thread.
        """
        self._running = False
        self._current_run_id = None
        self._queued_ids.discard(record.schedule_id)

        # Persist run record.
        self._store.save_run_record(record)

        # Recalculate next_run on the parent schedule.
        config = self._store.load_schedule(record.schedule_id)
        if config is not None:
            self._store.update_last_run(record.schedule_id, record.started_at)
            try:
                next_run = self._calculate_next_run(config)
            except ValueError as exc:
                logger.warning(
                    "Could not calculate next_run for %s: %s",
                    record.schedule_id,
                    exc,
                )
                next_run = None
            self._store.update_next_run(record.schedule_id, next_run)
            self.schedule_updated.emit(record.schedule_id)

        # Emit outcome signal.
        if record.status == RunStatus.SUCCESS:
            self.pipeline_completed.emit(
                record.schedule_id, record.schedule_name, True
            )
            logger.info(
                "Pipeline succeeded: %s (%s)", record.schedule_id, record.schedule_name
            )
        else:
            self.pipeline_failed.emit(
                record.schedule_id, record.schedule_name, record.error_message
            )
            logger.error(
                "Pipeline failed: %s (%s) — %s",
                record.schedule_id,
                record.schedule_name,
                record.error_message,
            )

        # Process next item in queue.
        self._execute_next()

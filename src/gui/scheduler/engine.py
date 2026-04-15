#!/usr/bin/env python3
"""
ScheduleEngine (API-Backed)
===========================

Lightweight polling engine that monitors pipelines and schedules via the
FastAPI backend.  No local execution — all jobs run through Celery workers
on the API side.

The engine polls ``GET /api/pipelines`` and ``GET /api/schedules`` every
30 seconds and emits Qt signals so the GUI can react to lifecycle events.

``trigger_now()`` posts to the API to trigger immediate execution, then
returns the resulting job ID so the GUI can stream logs via ``ApiWorker``.

Version 2.0 Changes:
- Removed local ``PipelineExecutor`` and ``_RunnerThread``
- All execution delegated to API via ``gui.api.pipeline`` / ``gui.api.scheduler``
- Engine now purely observational (poll + signal)
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from PySide6.QtCore import QObject, QTimer, Signal

from gui.api.client import ApiClient

logger = logging.getLogger(__name__)


class ScheduleEngine(QObject):
    """API-backed schedule engine that polls for status updates.

    Signals:
        pipeline_started (str, str): ``(pipeline_id, name)``
        pipeline_completed (str, str, bool): ``(pipeline_id, name, success)``
        pipeline_failed (str, str, str): ``(pipeline_id, name, error)``
        schedule_updated (str): ``(schedule_id)``
        data_refreshed (): Emitted after each poll cycle.

    Args:
        api_client: Shared API client instance.
        poll_interval: Polling interval in milliseconds (default 30 000).
        parent: Optional parent QObject.
    """

    pipeline_started = Signal(str, str)
    pipeline_completed = Signal(str, str, bool)
    pipeline_failed = Signal(str, str, str)
    schedule_updated = Signal(str)
    data_refreshed = Signal()

    def __init__(
        self,
        api_client: ApiClient,
        poll_interval: int = 30_000,
        parent: Optional[QObject] = None,
    ) -> None:
        super().__init__(parent)
        self._client = api_client
        self._timer = QTimer(self)
        self._timer.setInterval(poll_interval)
        self._timer.timeout.connect(self._tick)

        # Cache last-known statuses to detect transitions.
        self._pipeline_statuses: Dict[str, str] = {}
        self._schedule_statuses: Dict[str, str] = {}

        # Latest API data (consumed by the tab panels).
        self.pipelines: List[Dict[str, Any]] = []
        self.schedules: List[Dict[str, Any]] = []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Start polling for schedule/pipeline status."""
        logger.info("ScheduleEngine starting (poll interval=%dms)", self._timer.interval())
        self._timer.start()
        self._tick()

    def stop(self) -> None:
        """Stop the polling timer."""
        logger.info("ScheduleEngine stopping.")
        self._timer.stop()

    def trigger_pipeline(self, pipeline_id: str) -> Optional[str]:
        """Trigger a pipeline to run now via the API.

        Args:
            pipeline_id: UUID string.

        Returns:
            Job ID string on success, ``None`` on failure.
        """
        try:
            from gui.api.pipeline import trigger_pipeline

            result = trigger_pipeline(self._client, pipeline_id)
            job_id = result.get("jobId") or result.get("id")
            logger.info("Triggered pipeline %s → job %s", pipeline_id, job_id)
            self._tick()  # Refresh immediately
            return job_id
        except Exception as exc:
            logger.error("Failed to trigger pipeline %s: %s", pipeline_id, exc)
            return None

    def trigger_schedule(self, schedule_id: str) -> Optional[str]:
        """Trigger a schedule to run now via the API.

        Args:
            schedule_id: UUID string.

        Returns:
            Job ID string on success, ``None`` on failure.
        """
        try:
            from gui.api.scheduler import trigger_schedule

            result = trigger_schedule(self._client, schedule_id)
            job_id = result.get("jobId") or result.get("id")
            logger.info("Triggered schedule %s → job %s", schedule_id, job_id)
            self._tick()
            return job_id
        except Exception as exc:
            logger.error("Failed to trigger schedule %s: %s", schedule_id, exc)
            return None

    def toggle_pipeline(self, pipeline_id: str) -> bool:
        """Toggle a pipeline's active state.

        Returns:
            ``True`` on success.
        """
        try:
            from gui.api.pipeline import toggle_pipeline

            toggle_pipeline(self._client, pipeline_id)
            self._tick()
            return True
        except Exception as exc:
            logger.error("Failed to toggle pipeline %s: %s", pipeline_id, exc)
            return False

    def toggle_schedule(self, schedule_id: str) -> bool:
        """Toggle a schedule's active state.

        Returns:
            ``True`` on success.
        """
        try:
            from gui.api.scheduler import toggle_schedule

            toggle_schedule(self._client, schedule_id)
            self._tick()
            return True
        except Exception as exc:
            logger.error("Failed to toggle schedule %s: %s", schedule_id, exc)
            return False

    def delete_pipeline(self, pipeline_id: str) -> bool:
        """Delete a pipeline via the API.

        Returns:
            ``True`` on success.
        """
        try:
            from gui.api.pipeline import delete_pipeline

            delete_pipeline(self._client, pipeline_id)
            self._tick()
            return True
        except Exception as exc:
            logger.error("Failed to delete pipeline %s: %s", pipeline_id, exc)
            return False

    def delete_schedule(self, schedule_id: str) -> bool:
        """Delete a schedule via the API.

        Returns:
            ``True`` on success.
        """
        try:
            from gui.api.scheduler import delete_schedule

            delete_schedule(self._client, schedule_id)
            self._tick()
            return True
        except Exception as exc:
            logger.error("Failed to delete schedule %s: %s", schedule_id, exc)
            return False

    # ------------------------------------------------------------------
    # Polling
    # ------------------------------------------------------------------

    def _tick(self) -> None:
        """Fetch latest pipelines and schedules from the API."""
        self._poll_pipelines()
        self._poll_schedules()
        self.data_refreshed.emit()

    def _poll_pipelines(self) -> None:
        """Fetch pipelines and detect status transitions."""
        try:
            from gui.api.pipeline import list_pipelines

            self.pipelines = list_pipelines(self._client)
        except Exception as exc:
            logger.debug("Pipeline poll failed: %s", exc)
            return

        for p in self.pipelines:
            pid = p.get("id", "")
            name = p.get("name", "")
            status = p.get("lastStatus", "")
            prev = self._pipeline_statuses.get(pid)

            if prev != status and status:
                if status == "running":
                    self.pipeline_started.emit(pid, name)
                elif status == "success":
                    self.pipeline_completed.emit(pid, name, True)
                elif status == "failed":
                    self.pipeline_failed.emit(
                        pid, name, p.get("lastError", "Unknown error")
                    )

            self._pipeline_statuses[pid] = status

    def _poll_schedules(self) -> None:
        """Fetch schedules and detect status transitions."""
        try:
            from gui.api.scheduler import list_schedules

            self.schedules = list_schedules(self._client)
        except Exception as exc:
            logger.debug("Schedule poll failed: %s", exc)
            return

        for s in self.schedules:
            sid = s.get("id", "")
            status = s.get("lastStatus", "")
            prev = self._schedule_statuses.get(sid)
            if prev != status and status:
                self.schedule_updated.emit(sid)
            self._schedule_statuses[sid] = status

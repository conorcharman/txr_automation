#!/usr/bin/env python3
"""
Progress Tracking
=================

Provides a ProgressTracker utility for long-running tasks to report completion
percentage via Redis pub/sub to connected WebSocket clients.

This enables refresh scripts and other batch operations to emit structured
progress updates that are forwarded to the frontend in real time.

Version 1.0 Changes:
- Initial implementation for GLEIF/FIRDS refresh progress tracking

Usage:
    tracker = ProgressTracker(job_id)
    tracker.report_phase_progress("download", 50)  # 50% through download phase
    tracker.report_phase_progress("import", 100)   # Import phase complete
"""

import json
import logging
import os
from typing import Optional

import redis

logger = logging.getLogger(__name__)


class ProgressTracker:
    """
    Tracks and reports multi-phase task progress via Redis pub/sub.

    Each task has distinct phases (e.g., download, extract, parse, import).
    Each phase reports 0-100% completion independently. The tracker maps
    phase progress to global 0-100% by dividing the work equally.

    If Redis is unavailable or job_id is not provided, all reporting is
    silently ignored (no-op mode).

    Attributes:
        job_id: UUID of the associated job, or None if running locally.
        total_phases: Number of phases the task will go through.
        phase_to_global_percent: Maps phase index to global progress range.
    """

    def __init__(
        self,
        job_id: Optional[str] = None,
        total_phases: int = 4,
        redis_url: Optional[str] = None,
    ) -> None:
        """
        Initialize the progress tracker.

        Args:
            job_id: UUID string of the associated job. If None, tracking is
                disabled (no-op mode).
            total_phases: Number of phases expected (e.g., 4 for
                download/extract/parse/import).
            redis_url: Redis connection URL. If None, reads from REDIS_URL
                environment variable or uses default.
        """
        self.job_id = job_id
        self.total_phases = total_phases
        self._phase_index = 0
        self._last_reported_percent = 0
        self._redis_client: Optional[redis.Redis] = None

        if not self.job_id:
            logger.debug("ProgressTracker in no-op mode (no job_id provided)")
            return

        url = redis_url or os.environ.get("REDIS_URL", "redis://localhost:6379")
        try:
            self._redis_client = redis.from_url(url, decode_responses=False)
            # Verify connection
            self._redis_client.ping()
            logger.debug("ProgressTracker connected to Redis for job %s", job_id)
        except Exception as exc:
            logger.warning("Failed to connect to Redis for progress tracking: %s", exc)
            self._redis_client = None

    def report_phase_progress(self, phase_name: str, phase_percent: int) -> None:
        """
        Report progress within a single phase.

        Translates phase-specific progress (0-100) to global progress
        by computing which portion of the overall task this phase occupies.

        Example:
            With 4 phases, if phase 1 (index 0) is 50% complete:
            - Phase 0 spans global 0-25%
            - 50% of phase 0 = 12.5% globally → reported as 13%

        Args:
            phase_name: Human-readable name of the phase (e.g., "download").
            phase_percent: Completion percentage of this phase (0-100).
        """
        if not self.job_id or not self._redis_client:
            return

        # Clamp to valid range
        phase_percent = max(0, min(100, phase_percent))

        # Compute global percent: each phase gets an equal slice
        phase_size = 100 // self.total_phases
        global_percent = (self._phase_index * phase_size) + (
            phase_percent * phase_size // 100
        )
        global_percent = min(99, global_percent)  # Reserve 100 for completion

        # Only report if percent changed by >= 1%
        if global_percent <= self._last_reported_percent:
            return

        self._last_reported_percent = global_percent
        self._publish_progress(global_percent, phase_name)

    def advance_phase(self, phase_name: str) -> None:
        """
        Signal that the current phase is complete and moving to the next.

        Args:
            phase_name: Name of the phase that just completed.
        """
        if not self.job_id or not self._redis_client:
            return

        self.report_phase_progress(phase_name, 100)
        self._phase_index = min(self._phase_index + 1, self.total_phases - 1)
        logger.debug(
            "Advanced to phase %d (%s) for job %s",
            self._phase_index,
            phase_name,
            self.job_id,
        )

    def complete(self) -> None:
        """Signal that the task is complete and report 100%."""
        if not self.job_id or not self._redis_client:
            return

        self._publish_progress(100)
        logger.debug("Task complete for job %s", self.job_id)

    def _publish_progress(self, percent: int, phase_name: str = "") -> None:
        """
        Publish a progress update to Redis.

        Args:
            percent: Global completion percentage (0-100).
            phase_name: Optional phase name for logging.
        """
        if not self._redis_client or not self.job_id:
            return

        try:
            channel = f"job:{self.job_id}:logs"
            message = {"type": "progress", "data": percent}
            self._redis_client.publish(channel, json.dumps(message))
            if phase_name:
                logger.debug(
                    "Reported %d%% progress for job %s (phase: %s)",
                    percent,
                    self.job_id,
                    phase_name,
                )
        except Exception as exc:
            logger.warning(
                "Failed to publish progress for job %s: %s",
                self.job_id,
                exc,
            )

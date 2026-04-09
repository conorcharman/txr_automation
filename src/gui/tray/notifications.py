#!/usr/bin/env python3
"""
NotificationManager
===================

Sends Windows toast notifications for pipeline lifecycle events using the
``plyer`` library.  If ``plyer`` is not installed the manager degrades
gracefully: all notify calls become no-ops and a single warning is logged
at import time.

Version 1.0 Changes:
- Initial implementation for Phase 3 tray service
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Optional plyer import
# ---------------------------------------------------------------------------

try:
    from plyer import notification as _plyer_notification  # type: ignore[import]
    _PLYER_AVAILABLE = True
except ImportError:
    _plyer_notification = None  # type: ignore[assignment]
    _PLYER_AVAILABLE = False
    logger.warning(
        "plyer is not installed — toast notifications will be disabled. "
        "Install with: pip install plyer"
    )


class NotificationManager:
    """Sends Windows toast notifications for pipeline events.

    Uses :mod:`plyer.notification` to deliver native Windows toast messages.
    If ``plyer`` is unavailable at import time all notify methods silently
    do nothing so the tray continues to function without notifications.

    Example:
        >>> notifier = NotificationManager()
        >>> notifier.notify_started("Daily FCA Export")
        >>> notifier.notify_success("Daily FCA Export", 42.5, "3 files written")
        >>> notifier.notify_failure("Daily FCA Export", "Connection refused")
    """

    _APP_NAME = "TXR Automation"
    _TIMEOUT = 5  # seconds

    def __init__(self) -> None:
        self._available: bool = _PLYER_AVAILABLE

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def notify_started(self, schedule_name: str) -> None:
        """Notify that a pipeline has started.

        Args:
            schedule_name: Human-readable name of the schedule.
        """
        self._send(
            title=f"Pipeline started — {schedule_name}",
            message="Running scheduled pipeline…",
        )

    def notify_success(
        self,
        schedule_name: str,
        duration_seconds: float,
        summary: str = "",
    ) -> None:
        """Notify successful pipeline completion.

        Args:
            schedule_name: Human-readable name of the schedule.
            duration_seconds: Wall-clock seconds the pipeline took.
            summary: Optional short summary of outputs produced.
        """
        duration_str = _format_duration(duration_seconds)
        message = f"Completed in {duration_str}."
        if summary:
            message = f"{summary}  [{duration_str}]"
        self._send(
            title=f"Pipeline succeeded — {schedule_name}",
            message=message,
        )

    def notify_failure(
        self,
        schedule_name: str,
        error_message: str,
    ) -> None:
        """Notify pipeline failure.

        Args:
            schedule_name: Human-readable name of the schedule.
            error_message: Short description of the error that occurred.
        """
        # Truncate long error messages so they fit in the toast.
        truncated = error_message[:120] + "…" if len(error_message) > 120 else error_message
        self._send(
            title=f"Pipeline FAILED — {schedule_name}",
            message=truncated or "An unknown error occurred.",
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _send(self, title: str, message: str) -> None:
        """Dispatch a single toast notification.

        Args:
            title: Notification title shown in bold.
            message: Notification body text.
        """
        if not self._available or _plyer_notification is None:
            logger.debug("Notification suppressed (plyer unavailable): %s", title)
            return
        try:
            _plyer_notification.notify(
                title=title,
                message=message,
                app_name=self._APP_NAME,
                timeout=self._TIMEOUT,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to send notification '%s': %s", title, exc)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _format_duration(seconds: float) -> str:
    """Format a duration in seconds as a human-readable string.

    Args:
        seconds: Duration in seconds.

    Returns:
        Formatted string such as ``"42s"`` or ``"1m 23s"``.
    """
    secs = int(seconds)
    if secs < 60:
        return f"{secs}s"
    minutes, secs = divmod(secs, 60)
    return f"{minutes}m {secs}s"

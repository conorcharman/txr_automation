#!/usr/bin/env python3
"""
Tray Service Package
====================

System tray background service for TXR Automation.

Runs the :class:`~src.gui.scheduler.ScheduleEngine` in the background when
the main GUI window is closed, keeps schedules alive, and sends Windows toast
notifications on pipeline lifecycle events.

Exports:
    TrayApp: Main :class:`~PySide6.QtWidgets.QApplication` subclass.
    NotificationManager: Toast notification helper.
    AutoStartManager: Windows login auto-start via registry Run key.
"""

from __future__ import annotations

from typing import Any

__all__ = [
    "AutoStartManager",
    "NotificationManager",
    "TrayApp",
]


def __getattr__(name: str) -> Any:
    """Lazily import tray exports to avoid heavy GUI imports on module load."""
    if name == "AutoStartManager":
        from src.gui.tray.autostart import AutoStartManager

        return AutoStartManager
    if name == "NotificationManager":
        from src.gui.tray.notifications import NotificationManager

        return NotificationManager
    if name == "TrayApp":
        from src.gui.tray.tray_app import TrayApp

        return TrayApp
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

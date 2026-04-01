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

from src.gui.tray.autostart import AutoStartManager
from src.gui.tray.notifications import NotificationManager
from src.gui.tray.tray_app import TrayApp

__all__ = [
    "AutoStartManager",
    "NotificationManager",
    "TrayApp",
]

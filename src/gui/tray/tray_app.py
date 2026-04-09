#!/usr/bin/env python3
"""
TrayApp
=======

System tray background application for TXR Automation.

Runs a :class:`~src.gui.scheduler.ScheduleEngine` in the background without
showing a visible window.  A :class:`~PySide6.QtWidgets.QSystemTrayIcon`
provides a context menu to open the GUI, inspect upcoming runs, pause/resume
the scheduler, view recent run history, and quit.

A named Win32 mutex (``TXRAutomationTrayMutex``) ensures only one instance
runs at a time; a second launch prints a message and exits immediately.

Usage:
    txr-tray
    python -m src.gui.tray.tray_app

Version 1.0 Changes:
- Initial implementation for Phase 3 tray service
"""

from __future__ import annotations

import ctypes
import logging
import sys

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor, QIcon, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QHeaderView,
    QLabel,
    QMenu,
    QPushButton,
    QSystemTrayIcon,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from src.gui.scheduler import RunStatus, ScheduleEngine, ScheduleStore
from src.gui.tray.autostart import AutoStartManager
from src.gui.tray.notifications import NotificationManager

logger = logging.getLogger(__name__)

MUTEX_NAME = "TXRAutomationTrayMutex"

# Synchronise mutex access flags
_MUTEX_SYNCHRONIZE = 0x00100000


# ---------------------------------------------------------------------------
# Single-instance guard
# ---------------------------------------------------------------------------

def is_tray_running() -> bool:
    """Check whether a tray instance is already running via named mutex.

    Returns:
        ``True`` when another instance owns the mutex, ``False`` otherwise.
    """
    handle = ctypes.windll.kernel32.OpenMutexW(_MUTEX_SYNCHRONIZE, False, MUTEX_NAME)
    if handle:
        ctypes.windll.kernel32.CloseHandle(handle)
        return True
    return False


# ---------------------------------------------------------------------------
# Icon factory
# ---------------------------------------------------------------------------

_ICON_COLOURS: dict[str, str] = {
    "grey": "#6A737B",
    "green": "#2E7D32",
    "red": "#D50032",
}


def _make_icon(colour: str) -> QIcon:
    """Create a small filled-circle icon in the given colour.

    Args:
        colour: One of ``"grey"``, ``"green"``, or ``"red"``.

    Returns:
        :class:`~PySide6.QtGui.QIcon` instance.
    """
    hex_colour = _ICON_COLOURS.get(colour, _ICON_COLOURS["grey"])
    px = QPixmap(16, 16)
    px.fill(QColor(hex_colour))
    return QIcon(px)


# ---------------------------------------------------------------------------
# Recent runs dialog
# ---------------------------------------------------------------------------

class RecentRunsDialog(QDialog):
    """Small dialog showing the last 10 pipeline runs.

    Args:
        store: :class:`~src.gui.scheduler.ScheduleStore` to query.
        parent: Optional parent widget.
    """

    def __init__(self, store: ScheduleStore, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Recent Runs — TXR Automation")
        self.resize(640, 320)

        layout = QVBoxLayout(self)

        table = QTableWidget(0, 4)
        table.setHorizontalHeaderLabels(["Schedule", "Started", "Duration", "Status"])
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setAlternatingRowColors(True)

        history = store.get_all_run_history(limit=10)
        for run in history:
            row = table.rowCount()
            table.insertRow(row)
            table.setItem(row, 0, QTableWidgetItem(run.schedule_name))
            table.setItem(row, 1, QTableWidgetItem(run.started_at.strftime("%Y-%m-%d %H:%M")))

            duration = ""
            if run.completed_at:
                secs = int((run.completed_at - run.started_at).total_seconds())
                duration = f"{secs}s"
            table.setItem(row, 2, QTableWidgetItem(duration))

            status_item = QTableWidgetItem(run.status.value.upper())
            colour = {"success": "#2E7D32", "failed": "#D50032"}.get(
                run.status.value, "#6A737B"
            )
            status_item.setForeground(QColor(colour))
            table.setItem(row, 3, status_item)

        layout.addWidget(table)

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn, alignment=Qt.AlignmentFlag.AlignRight)


# ---------------------------------------------------------------------------
# Main application
# ---------------------------------------------------------------------------

class TrayApp(QApplication):
    """System tray application that runs scheduled pipelines in the background.

    Creates a :class:`~PySide6.QtWidgets.QSystemTrayIcon` with a context menu
    and integrates the :class:`~src.gui.scheduler.ScheduleEngine` so schedules
    execute without the GUI window being open.

    Args:
        argv: Command-line arguments forwarded to :class:`QApplication`.
    """

    def __init__(self, argv: list[str]) -> None:
        super().__init__(argv)
        self.setQuitOnLastWindowClosed(False)

        # Claim the named mutex so is_tray_running() returns True for sibling
        # processes that start after us.
        self._mutex = ctypes.windll.kernel32.CreateMutexW(None, False, MUTEX_NAME)

        self._store = ScheduleStore()
        self._engine = ScheduleEngine(self._store)
        self._notifier = NotificationManager()
        self._paused = False

        # Wire engine signals.
        self._engine.pipeline_started.connect(self._on_started)
        self._engine.pipeline_completed.connect(self._on_completed)
        self._engine.pipeline_failed.connect(self._on_failed)

        # Build tray icon.
        self._tray = QSystemTrayIcon(self)
        self._tray.setIcon(_make_icon("grey"))
        self._tray.setToolTip("TXR Automation — Scheduler")
        self._tray.setContextMenu(self._build_menu())
        self._tray.show()

        self._engine.start()
        logger.info("TrayApp started.")

    # ------------------------------------------------------------------
    # Menu construction
    # ------------------------------------------------------------------

    def _build_menu(self) -> QMenu:
        """Build the right-click context menu.

        Returns:
            Populated :class:`~PySide6.QtWidgets.QMenu`.
        """
        menu = QMenu()
        menu.addAction("Open TXR Automation GUI", self._open_gui)

        self._next_run_action = menu.addAction("Next run: —")
        self._next_run_action.setEnabled(False)

        menu.addSeparator()

        self._pause_action = menu.addAction("Pause all schedules", self._toggle_pause)
        menu.addAction("Recent runs\u2026", self._show_recent_runs)

        menu.addSeparator()

        # Auto-start toggle
        self._autostart_action = menu.addAction(
            "Start on login", self._toggle_autostart
        )
        self._autostart_action.setCheckable(True)
        self._autostart_action.setChecked(AutoStartManager.is_enabled())

        menu.addSeparator()
        menu.addAction("Quit", self._quit)

        # Refresh "Next run" label every 30 s.
        self._menu_timer = QTimer(self)
        self._menu_timer.setInterval(30_000)
        self._menu_timer.timeout.connect(self._refresh_next_run_label)
        self._menu_timer.start()
        self._refresh_next_run_label()

        return menu

    # ------------------------------------------------------------------
    # Engine signal handlers
    # ------------------------------------------------------------------

    def _on_started(self, schedule_id: str, schedule_name: str) -> None:
        """Handle pipeline-started signal.

        Args:
            schedule_id: UUID of the schedule that started.
            schedule_name: Display name of the schedule.
        """
        self._tray.setIcon(_make_icon("green"))
        self._tray.setToolTip(f"TXR Automation — Running: {schedule_name}")
        self._notifier.notify_started(schedule_name)

    def _on_completed(
        self,
        schedule_id: str,
        schedule_name: str,
        success: bool,
    ) -> None:
        """Handle pipeline-completed signal.

        Args:
            schedule_id: UUID of the completed schedule.
            schedule_name: Display name of the schedule.
            success: ``True`` when the pipeline succeeded.
        """
        self._tray.setIcon(_make_icon("grey" if success else "red"))
        self._tray.setToolTip("TXR Automation — Scheduler")

        history = self._store.get_run_history(schedule_id, limit=1)
        duration = 0.0
        if history and history[0].completed_at and history[0].started_at:
            duration = (
                history[0].completed_at - history[0].started_at
            ).total_seconds()

        if success:
            self._notifier.notify_success(schedule_name, duration)
        else:
            run = history[0] if history else None
            error_msg = run.error_message if run else "Unknown error"
            self._notifier.notify_failure(schedule_name, error_msg)

    def _on_failed(
        self,
        schedule_id: str,
        schedule_name: str,
        error: str,
    ) -> None:
        """Handle pipeline-failed signal.

        Args:
            schedule_id: UUID of the failed schedule.
            schedule_name: Display name of the schedule.
            error: Error message from the engine.
        """
        self._tray.setIcon(_make_icon("red"))
        self._tray.setToolTip(f"TXR Automation — Last run FAILED: {schedule_name}")
        self._notifier.notify_failure(schedule_name, error)

    # ------------------------------------------------------------------
    # Menu action handlers
    # ------------------------------------------------------------------

    def _open_gui(self) -> None:
        """Launch the main TXR Automation GUI in a separate process."""
        import subprocess  # noqa: PLC0415

        subprocess.Popen([sys.executable, "-m", "src.gui.app"])  # noqa: S603

    def _toggle_pause(self) -> None:
        """Pause or resume all schedule execution."""
        if self._paused:
            self._engine.start()
            self._paused = False
            self._pause_action.setText("Pause all schedules")
            self._tray.setIcon(_make_icon("grey"))
            logger.info("Scheduler resumed.")
        else:
            self._engine.stop()
            self._paused = True
            self._pause_action.setText("Resume all schedules")
            self._tray.setIcon(_make_icon("grey"))
            logger.info("Scheduler paused.")

    def _refresh_next_run_label(self) -> None:
        """Update the 'Next run' text in the context menu."""
        schedules = [
            s for s in self._store.list_schedules() if s.enabled and s.next_run
        ]
        if not schedules:
            self._next_run_action.setText("Next run: none scheduled")
            return
        next_schedule = min(schedules, key=lambda s: s.next_run)  # type: ignore[arg-type]
        self._next_run_action.setText(
            f"Next run: {next_schedule.name} at "
            f"{next_schedule.next_run.strftime('%H:%M')}"  # type: ignore[union-attr]
        )

    def _show_recent_runs(self) -> None:
        """Open the recent-runs dialog."""
        dialog = RecentRunsDialog(self._store)
        dialog.exec()

    def _toggle_autostart(self) -> None:
        """Toggle the Windows login auto-start setting."""
        if AutoStartManager.is_enabled():
            success = AutoStartManager.disable()
        else:
            success = AutoStartManager.enable()

        # Sync checkbox to actual state (in case the registry call failed).
        self._autostart_action.setChecked(AutoStartManager.is_enabled())

        if not success:
            logger.warning("Failed to toggle auto-start setting.")

    def _quit(self) -> None:
        """Stop the engine, release the mutex, and exit."""
        self._engine.stop()
        if self._mutex:
            ctypes.windll.kernel32.ReleaseMutex(self._mutex)
            ctypes.windll.kernel32.CloseHandle(self._mutex)
            self._mutex = None
        logger.info("TrayApp quit.")
        self.quit()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    """Entry point for the ``txr-tray`` console script.

    Checks for a pre-existing instance via the named mutex and exits
    immediately if one is found.
    """
    if is_tray_running():
        print("TXR Automation tray is already running.")
        sys.exit(0)

    app = TrayApp(sys.argv)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()

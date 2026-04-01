#!/usr/bin/env python3
"""
TXR Automation GUI — Main Application
======================================

QApplication + QMainWindow with a QTabWidget containing all script tabs,
a menu bar (File, Help), and a status bar.

Usage:
    python -m gui
"""

import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QApplication,
    QLabel,
    QMainWindow,
    QMenuBar,
    QMessageBox,
    QStatusBar,
    QTabWidget,
)

from gui.constants import (
    APP_NAME,
    APP_VERSION,
    DEFAULT_WINDOW_SIZE,
    STATUS_READY,
)
from gui.tabs import AccuracyTab, FirdsTab, GleifTab, ReplayTab, UtilitiesTab
from gui.theme import apply_mica, apply_theme


class MainWindow(QMainWindow):
    """Main application window containing all script tabs."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.setMinimumSize(*DEFAULT_WINDOW_SIZE)

        # Central tab widget
        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)

        self.tabs.addTab(AccuracyTab(), "Accuracy Testing")
        self.tabs.addTab(ReplayTab(), "Replay")
        self.tabs.addTab(FirdsTab(), "FIRDS Reportability Data")
        self.tabs.addTab(GleifTab(), "GLEIF Reference Data")
        self.tabs.addTab(UtilitiesTab(), "Utilities")

        self._create_menu_bar()
        self._create_status_bar()

    def closeEvent(self, event: QCloseEvent) -> None:
        """Stop all running worker threads before closing."""
        self._stop_all_workers()
        super().closeEvent(event)

    def _stop_all_workers(self) -> None:
        """Find and stop every ScriptRunnerWorker still running."""
        from gui.workers import ScriptRunnerWorker

        for widget in self.findChildren(ScriptRunnerWorker):
            if widget.isRunning():
                widget.cancel()
                widget.wait(3000)

    def _create_menu_bar(self) -> None:
        """Build the File and Help menus."""
        menu_bar = self.menuBar()

        # File menu
        file_menu = menu_bar.addMenu("&File")

        exit_action = file_menu.addAction("E&xit")
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)

        # Help menu
        help_menu = menu_bar.addMenu("&Help")

        about_action = help_menu.addAction("&About")
        about_action.triggered.connect(self._show_about)

    def showEvent(self, event) -> None:  # type: ignore[override]
        """Apply Mica background on Windows 11 after the window is visible."""
        super().showEvent(event)
        apply_mica(self)

    def _create_status_bar(self) -> None:
        """Build the status bar with ready message."""
        status = self.statusBar()
        self._status_label = QLabel(STATUS_READY)
        status.addWidget(self._status_label)

    def _show_about(self) -> None:
        """Show the About dialog."""
        QMessageBox.about(
            self,
            f"About {APP_NAME}",
            f"<b>{APP_NAME}</b> v{APP_VERSION}<br><br>"
            f"Desktop GUI for TXR Automation scripts.<br>"
            f"Python {sys.version.split()[0]}<br>"
            f"Qt (PySide6)",
        )


def main() -> None:
    """Application entry point."""
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)
    apply_theme(app)

    window = MainWindow()
    window.show()

    ret = app.exec()
    # Ensure Qt objects are destroyed before Python GC runs,
    # preventing 'QThread: Destroyed while thread is still running'.
    del window
    del app
    sys.exit(ret)


if __name__ == "__main__":
    main()

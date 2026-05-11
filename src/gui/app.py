#!/usr/bin/env python3
"""
TXR Automation GUI — Main Application
======================================

QApplication + QMainWindow with a QTabWidget containing all script tabs,
a menu bar (File, Help), a status bar with API connection indicator,
and a background health check timer.

Usage:
    python -m gui
"""

import sys
from typing import Optional

from PySide6.QtCore import Qt, QThread, QTimer, Signal
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenuBar,
    QMessageBox,
    QPushButton,
    QStatusBar,
    QTabWidget,
    QVBoxLayout,
)

from gui.api.client import ApiClient
from gui.constants import (
    API_DEFAULT_URL,
    APP_NAME,
    APP_VERSION,
    DEFAULT_WINDOW_SIZE,
    STATUS_READY,
)
from gui.tabs import AccuracyTab, FcaTab, FileBrowserTab, FirdsTab, GleifTab, ReconciliationTab, ReplayTab, SchedulerTab, UtilitiesTab
from gui.theme import apply_mica, apply_theme
from gui.utils.settings import settings


class _HealthCheckWorker(QThread):
    """Background thread that pings the API without blocking the main thread."""

    result = Signal(bool)

    def __init__(self, client: "ApiClient", parent=None) -> None:
        super().__init__(parent)
        self._client = client

    def run(self) -> None:  # noqa: D102
        # Use a short timeout so the thread finishes quickly when offline.
        import requests

        try:
            resp = self._client._session.get(
                self._client._url("/api/health"), timeout=3
            )
            data = resp.json() if resp.ok else {}
            self.result.emit(isinstance(data, dict) and data.get("status") == "ok")
        except Exception:
            self.result.emit(False)


class ApiSettingsDialog(QDialog):
    """Dialog for configuring the API backend URL."""

    def __init__(self, current_url: str, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("API Settings")
        self.setMinimumWidth(420)

        layout = QVBoxLayout(self)

        form = QFormLayout()
        self._url_edit = QLineEdit(current_url)
        self._url_edit.setPlaceholderText(API_DEFAULT_URL)
        form.addRow("API URL:", self._url_edit)
        layout.addLayout(form)

        # Test connection button + status label
        test_row = QHBoxLayout()
        self._test_btn = QPushButton("Test Connection")
        self._test_btn.clicked.connect(self._test_connection)
        self._test_status = QLabel("")
        test_row.addWidget(self._test_btn)
        test_row.addWidget(self._test_status, 1)
        layout.addLayout(test_row)

        # Standard OK / Cancel
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    @property
    def url(self) -> str:
        """Return the entered URL (stripped)."""
        return self._url_edit.text().strip()

    def _test_connection(self) -> None:
        """Test the connection to the API."""
        self._test_status.setText("Connecting...")
        self._test_status.repaint()

        client = ApiClient(base_url=self.url, timeout=5)
        if client.health_check():
            self._test_status.setText("\u2705 Connected")
            self._test_status.setObjectName("api-connected")
        else:
            self._test_status.setText("\u274c Unreachable")
            self._test_status.setObjectName("api-offline")
        self._test_status.style().unpolish(self._test_status)
        self._test_status.style().polish(self._test_status)


class MainWindow(QMainWindow):
    """Main application window containing all script tabs."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.setMinimumSize(*DEFAULT_WINDOW_SIZE)

        # Shared API client (all tabs will use this)
        self.api_client = ApiClient()

        # Central tab widget
        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)

        self.tabs.addTab(AccuracyTab(api_client=self.api_client), "Accuracy Testing")
        self.tabs.addTab(ReplayTab(), "Replay")
        self.tabs.addTab(FirdsTab(), "FIRDS Reportability Data")
        self.tabs.addTab(GleifTab(), "GLEIF Reference Data")
        self.tabs.addTab(FcaTab(), "FCA Register")
        self.tabs.addTab(UtilitiesTab(), "Utilities")
        self.tabs.addTab(SchedulerTab(api_client=self.api_client), "Scheduler")
        self.tabs.addTab(ReconciliationTab(api_client=self.api_client), "Reconciliation")
        self.tabs.addTab(FileBrowserTab(api_client=self.api_client), "Output Files")

        self._create_menu_bar()
        self._create_status_bar()
        self._setup_health_check()

    def closeEvent(self, event: QCloseEvent) -> None:
        """Stop all running worker threads before closing."""
        self._health_timer.stop()
        if self._health_worker and self._health_worker.isRunning():
            self._health_worker.wait(4000)
        self._stop_all_workers()
        super().closeEvent(event)

    def _stop_all_workers(self) -> None:
        """Find and stop every running worker thread."""
        from gui.workers import ApiWorker, ScriptRunnerWorker

        for worker_cls in (ScriptRunnerWorker, ApiWorker):
            for widget in self.findChildren(worker_cls):
                if widget.isRunning():
                    widget.cancel()
                    widget.wait(3000)

    def _create_menu_bar(self) -> None:
        """Build the File and Help menus."""
        menu_bar = self.menuBar()

        # File menu
        file_menu = menu_bar.addMenu("&File")

        api_settings_action = file_menu.addAction("API &Settings...")
        api_settings_action.triggered.connect(self._show_api_settings)

        file_menu.addSeparator()

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
        """Build the status bar with ready message and API indicator."""
        status = self.statusBar()

        self._status_label = QLabel(STATUS_READY)
        status.addWidget(self._status_label, 1)

        # API connection indicator (right side)
        self._api_indicator = QLabel("\u25cf API: Checking...")
        self._api_indicator.setObjectName("api-offline")
        status.addPermanentWidget(self._api_indicator)

    def _setup_health_check(self) -> None:
        """Set up a 60-second health check timer + immediate first check."""
        self._health_timer = QTimer(self)
        self._health_timer.timeout.connect(self._check_api_health)
        self._health_timer.start(60_000)  # 60 seconds
        self._health_worker: Optional[_HealthCheckWorker] = None

        # Run the first check after a short delay (let the window paint first)
        QTimer.singleShot(500, self._check_api_health)

    def _check_api_health(self) -> None:
        """Ping the API in a background thread so the main thread is never blocked."""
        if self._health_worker and self._health_worker.isRunning():
            return  # Previous check still in progress; skip this cycle.
        self._health_worker = _HealthCheckWorker(self.api_client, parent=self)
        self._health_worker.result.connect(self._on_health_result)
        self._health_worker.start()

    def _on_health_result(self, connected: bool) -> None:
        """Update the status bar indicator with the health check result."""
        if connected:
            self._api_indicator.setText("\u25cf API: Connected")
            self._api_indicator.setObjectName("api-connected")
        else:
            self._api_indicator.setText("\u25cf API: Offline")
            self._api_indicator.setObjectName("api-offline")
        self._api_indicator.style().unpolish(self._api_indicator)
        self._api_indicator.style().polish(self._api_indicator)

    def _show_api_settings(self) -> None:
        """Show the API settings dialog."""
        dialog = ApiSettingsDialog(self.api_client.base_url, parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            new_url = dialog.url or API_DEFAULT_URL
            self.api_client.base_url = new_url
            self._check_api_health()

    def _show_about(self) -> None:
        """Show the About dialog."""
        QMessageBox.about(
            self,
            f"About {APP_NAME}",
            f"<b>{APP_NAME}</b> v{APP_VERSION}<br><br>"
            f"Desktop GUI for TXR Automation scripts.<br>"
            f"API: {self.api_client.base_url}<br>"
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

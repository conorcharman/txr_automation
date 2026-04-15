#!/usr/bin/env python3
"""
FIRDS Reference Data Tab
=========================

Three FIRDS reference data script panels:
- Cache Refresh
- Reportability Check (single and batch modes)
- Backfill
"""

from typing import Any, Dict, List, Optional

from PySide6.QtWidgets import (
    QButtonGroup,
    QDateEdit,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QRadioButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtCore import QDate

from gui.api.client import ApiClient
from gui.constants import LOG_LEVELS, CSV_FILTER, SQLITE_FILTER, YAML_FILTER
from gui.widgets import (
    ConfigLoaderWidget,
    FilePickerWidget,
    FormFieldWidget,
    LogViewerWidget,
    RunControlsWidget,
)
from gui.workers import ApiWorker


# ---------------------------------------------------------------------------
# Cache Refresh panel
# ---------------------------------------------------------------------------

class CacheRefreshPanel(QWidget):
    """Panel for the FIRDS cache refresh script."""

    def __init__(self, api_client: ApiClient, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._client = api_client
        self._worker: Optional[ApiWorker] = None
        pfx = "firds.cache_refresh"

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("<b>FIRDS Cache Refresh</b>"))

        self.config_loader = ConfigLoaderWidget()
        layout.addWidget(self.config_loader)

        self.refresh_type = FormFieldWidget(
            "Refresh Type:", field_type="dropdown",
            choices=["full"], default="full",
            tooltip="Type of cache refresh to perform.",
            settings_key=f"{pfx}.refresh_type",
        )
        layout.addWidget(self.refresh_type)

        # Date picker (Saturdays only validated in tooltip/label)
        date_row = QHBoxLayout()
        date_label = QLabel("Publication Date:")
        date_label.setFixedWidth(140)
        date_row.addWidget(date_label)
        self._date_edit = QDateEdit()
        self._date_edit.setCalendarPopup(True)
        self._date_edit.setDate(QDate.currentDate())
        self._date_edit.setDisplayFormat("yyyy-MM-dd")
        date_row.addWidget(self._date_edit, stretch=1)
        self._date_warning = QLabel("")
        self._date_warning.setStyleSheet("color: orange;")
        date_row.addWidget(self._date_warning)
        layout.addLayout(date_row)
        self._date_edit.dateChanged.connect(self._check_saturday)

        self.db_path = FilePickerWidget(
            "Database Path:", mode="file", file_filter=SQLITE_FILTER,
            tooltip="Path to the FIRDS SQLite cache database.\nExample: firds_cache.db",
            settings_key=f"{pfx}.db_path",
        )
        layout.addWidget(self.db_path)

        self.staging_dir = FilePickerWidget(
            "Staging Directory:", mode="directory",
            tooltip="Temporary directory for downloading FIRDS data files.",
            settings_key=f"{pfx}.staging_dir",
        )
        layout.addWidget(self.staging_dir)

        self.log_level = FormFieldWidget(
            "Log Level:", field_type="dropdown",
            choices=LOG_LEVELS, default="INFO",
            tooltip="Logging verbosity level.",
            settings_key=f"{pfx}.log_level",
        )
        layout.addWidget(self.log_level)

        self.run_controls = RunControlsWidget()
        self.run_controls.run_clicked.connect(self._on_run)
        self.run_controls.cancel_clicked.connect(self._on_cancel)
        self.run_controls._dry_run_btn.setVisible(False)
        layout.addWidget(self.run_controls)

        self.log_viewer = LogViewerWidget()
        layout.addWidget(self.log_viewer, stretch=1)

    def _check_saturday(self, date: QDate) -> None:
        """Warn if the selected date is not a Saturday."""
        if date.dayOfWeek() != 6:
            self._date_warning.setText("⚠ Not a Saturday")
        else:
            self._date_warning.setText("")

    def build_argv(self) -> List[str]:
        argv: List[str] = ["--type", self.refresh_type.get_value()]

        date_str = self._date_edit.date().toString("yyyy-MM-dd")
        argv.extend(["--date", date_str])

        db = self.db_path.get_path()
        if db:
            argv.extend(["--db", db])

        staging = self.staging_dir.get_path()
        if staging:
            argv.extend(["--staging-dir", staging])

        config_path = self.config_loader.get_last_path()
        if config_path:
            argv.extend(["--config", config_path])

        log_level = self.log_level.get_value()
        if log_level:
            argv.extend(["--log-level", log_level])
        return argv

    def _on_run(self) -> None:
        payload = {
            "type": self.refresh_type.get_value(),
            "date": self._date_edit.date().toString("yyyy-MM-dd"),
            "dbPath": self.db_path.get_path(),
            "stagingDir": self.staging_dir.get_path(),
            "config": self.config_loader.get_last_path(),
            "logLevel": self.log_level.get_value(),
        }
        self.log_viewer.clear()
        self.log_viewer.append_line("[GUI] Running: firds-refresh")
        self.run_controls.set_running(True)
        self._worker = ApiWorker("/api/firds/refresh", payload, self._client)
        self._worker.output_line.connect(self.log_viewer.append_line)
        self._worker.finished_signal.connect(self._on_finished)
        self._worker.start()

    def _on_cancel(self) -> None:
        if self._worker and self._worker.isRunning():
            self._worker.terminate()
            self.log_viewer.append_error("[GUI] Cancelled by user")

    def _on_finished(self, success: bool) -> None:
        self.run_controls.set_running(False)
        if success:
            self.log_viewer.append_line("[GUI] Completed successfully")
        else:
            self.log_viewer.append_error("[GUI] Failed")
        self._worker = None


# ---------------------------------------------------------------------------
# Reportability Check panel (single + batch modes)
# ---------------------------------------------------------------------------

class ReportabilityCheckPanel(QWidget):
    """Panel for the FIRDS reportability check script."""

    def __init__(self, api_client: ApiClient, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._client = api_client
        self._worker: Optional[ApiWorker] = None

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("<b>FIRDS Reportability Check</b>"))

        self.config_loader = ConfigLoaderWidget()
        layout.addWidget(self.config_loader)

        # Mode selection
        mode_group = QGroupBox("Mode")
        mode_layout = QVBoxLayout(mode_group)
        self._single_radio = QRadioButton("Single Instrument")
        self._batch_radio = QRadioButton("Batch Processing")
        self._single_radio.setChecked(True)
        self._btn_group = QButtonGroup(self)
        self._btn_group.addButton(self._single_radio, 0)
        self._btn_group.addButton(self._batch_radio, 1)
        mode_layout.addWidget(self._single_radio)
        mode_layout.addWidget(self._batch_radio)
        layout.addWidget(mode_group)

        # Single mode fields
        self._single_widget = QWidget()
        single_layout = QVBoxLayout(self._single_widget)
        single_layout.setContentsMargins(0, 0, 0, 0)
        self.isin = FormFieldWidget(
            "ISIN:", field_type="text",
            tooltip="12-character International Securities Identification Number",
            settings_key="firds.reportability.isin",
        )
        single_layout.addWidget(self.isin)
        self.mic = FormFieldWidget(
            "MIC:", field_type="text",
            tooltip="Market Identifier Code, e.g. XLON",
            settings_key="firds.reportability.mic",
        )
        single_layout.addWidget(self.mic)

        date_row = QHBoxLayout()
        date_label = QLabel("Trade Date:")
        date_label.setFixedWidth(140)
        date_row.addWidget(date_label)
        self._trade_date = QDateEdit()
        self._trade_date.setCalendarPopup(True)
        self._trade_date.setDate(QDate.currentDate())
        self._trade_date.setDisplayFormat("yyyy-MM-dd")
        date_row.addWidget(self._trade_date, stretch=1)
        single_layout.addLayout(date_row)

        # Output choice for single mode
        self._single_output_group = QGroupBox("Output")
        single_out_layout = QVBoxLayout(self._single_output_group)
        self._display_radio = QRadioButton("Display in log")
        self._file_radio = QRadioButton("Write to file")
        self._display_radio.setChecked(True)
        self._single_out_btn_group = QButtonGroup(self)
        self._single_out_btn_group.addButton(self._display_radio, 0)
        self._single_out_btn_group.addButton(self._file_radio, 1)
        single_out_layout.addWidget(self._display_radio)
        single_out_layout.addWidget(self._file_radio)
        self.single_output_file = FilePickerWidget(
            "Output CSV:", mode="save", file_filter=CSV_FILTER,
            tooltip="e.g. reportability_result.csv",
            settings_key="firds.reportability.single_output",
        )
        self.single_output_file.setVisible(False)
        single_out_layout.addWidget(self.single_output_file)
        self._single_out_btn_group.idToggled.connect(self._on_single_output_changed)
        single_layout.addWidget(self._single_output_group)

        layout.addWidget(self._single_widget)

        # Batch mode fields
        self._batch_widget = QWidget()
        batch_layout = QVBoxLayout(self._batch_widget)
        batch_layout.setContentsMargins(0, 0, 0, 0)
        self.input_files = FilePickerWidget(
            "Input CSV:", mode="file", file_filter=CSV_FILTER,
            tooltip="Single CSV file containing ISIN column",
            settings_key="firds.reportability.input_files",
        )
        batch_layout.addWidget(self.input_files)
        self.input_dir = FilePickerWidget(
            "Input Directory:", mode="directory",
            tooltip="Directory of CSV files to process",
            settings_key="firds.reportability.input_dir",
        )
        batch_layout.addWidget(self.input_dir)
        self.glob_pattern = FormFieldWidget(
            "Glob Pattern:", field_type="text", default="*.csv",
            tooltip="File matching pattern for batch input, e.g. *.csv",
            settings_key="firds.reportability.glob_pattern",
        )
        batch_layout.addWidget(self.glob_pattern)
        self.output_file = FilePickerWidget(
            "Output CSV:", mode="save", file_filter=CSV_FILTER,
            tooltip="Output CSV with reportability results",
            settings_key="firds.reportability.output_file",
        )
        batch_layout.addWidget(self.output_file)
        layout.addWidget(self._batch_widget)
        self._batch_widget.setVisible(False)

        # Toggle mode visibility
        self._btn_group.idToggled.connect(self._on_mode_changed)

        # Common fields
        self.db_path = FilePickerWidget(
            "Database Path:", mode="file", file_filter=SQLITE_FILTER,
            tooltip="FIRDS SQLite cache database file",
            settings_key="firds.reportability.db_path",
        )
        layout.addWidget(self.db_path)

        self.log_level = FormFieldWidget(
            "Log Level:", field_type="dropdown",
            choices=LOG_LEVELS, default="WARNING",
            tooltip="Logging verbosity",
            settings_key="firds.reportability.log_level",
        )
        layout.addWidget(self.log_level)

        self.run_controls = RunControlsWidget()
        self.run_controls.run_clicked.connect(self._on_run)
        self.run_controls.cancel_clicked.connect(self._on_cancel)
        self.run_controls._dry_run_btn.setVisible(False)
        layout.addWidget(self.run_controls)

        self.log_viewer = LogViewerWidget()
        layout.addWidget(self.log_viewer, stretch=1)

    def _on_mode_changed(self, button_id: int, checked: bool) -> None:
        """Toggle between single and batch mode fields."""
        if not checked:
            return
        self._single_widget.setVisible(button_id == 0)
        self._batch_widget.setVisible(button_id == 1)

    def _on_single_output_changed(self, button_id: int, checked: bool) -> None:
        """Show/hide the output file picker for single mode."""
        if not checked:
            return
        self.single_output_file.setVisible(button_id == 1)

    def build_argv(self) -> List[str]:
        argv: List[str] = []

        if self._single_radio.isChecked():
            isin = self.isin.get_value()
            if isin:
                argv.extend(["--isin", isin])
            mic = self.mic.get_value()
            if mic:
                argv.extend(["--mic", mic])
            date_str = self._trade_date.date().toString("yyyy-MM-dd")
            argv.extend(["--date", date_str])
        else:
            input_path = self.input_files.get_path()
            if input_path:
                argv.extend(["--input", input_path])
            input_dir = self.input_dir.get_path()
            if input_dir:
                argv.extend(["--input-dir", input_dir])
            pattern = self.glob_pattern.get_value()
            if pattern and pattern != "*.csv":
                argv.extend(["--pattern", pattern])
            output = self.output_file.get_path()
            if output:
                argv.extend(["--output", output])

        db = self.db_path.get_path()
        if db:
            argv.extend(["--db", db])

        config_path = self.config_loader.get_last_path()
        if config_path:
            argv.extend(["--config", config_path])

        log_level = self.log_level.get_value()
        if log_level:
            argv.extend(["--log-level", log_level])
        return argv

    def _on_run(self) -> None:
        if self._single_radio.isChecked() and self._file_radio.isChecked():
            self._run_single_to_file()
            return

        if self._single_radio.isChecked():
            payload: Dict[str, Any] = {
                "mode": "single",
                "isin": self.isin.get_value(),
                "mic": self.mic.get_value(),
                "tradeDate": self._trade_date.date().toString("yyyy-MM-dd"),
                "dbPath": self.db_path.get_path(),
                "config": self.config_loader.get_last_path(),
                "logLevel": self.log_level.get_value(),
            }
        else:
            payload = {
                "mode": "batch",
                "inputFile": self.input_files.get_path(),
                "inputDir": self.input_dir.get_path(),
                "pattern": self.glob_pattern.get_value(),
                "outputFile": self.output_file.get_path(),
                "dbPath": self.db_path.get_path(),
                "config": self.config_loader.get_last_path(),
                "logLevel": self.log_level.get_value(),
            }
        self.log_viewer.clear()
        self.log_viewer.append_line("[GUI] Running: firds-check")
        self.run_controls.set_running(True)
        self._worker = ApiWorker("/api/firds/check", payload, self._client)
        self._worker.output_line.connect(self.log_viewer.append_line)
        self._worker.finished_signal.connect(self._on_finished)
        self._worker.start()

    def _run_single_to_file(self) -> None:
        """Run a single-ISIN lookup and write the result to CSV."""
        import csv
        from pathlib import Path

        output_path = self.single_output_file.get_path()
        if not output_path:
            self.log_viewer.append_error(
                "[GUI] No output file selected. Choose a file path first."
            )
            return

        isin = self.isin.get_value()
        if not isin:
            self.log_viewer.append_error("[GUI] ISIN is required.")
            return

        self.log_viewer.clear()
        self.log_viewer.append_line(
            f"[GUI] Looking up ISIN {isin} and writing to {output_path}"
        )
        self.run_controls.set_running(True)

        try:
            db = self.db_path.get_path()
            db_path = Path(db) if db else None
            if db_path is None or not db_path.exists():
                self.log_viewer.append_error(
                    f"[GUI] Database not found: {db_path}"
                )
                self.run_controls.set_running(False)
                return

            from firds.cache import FirdsCacheManager
            from firds.reportability import FirdsReportabilityChecker

            cache = FirdsCacheManager(db_path=db_path)
            cache.initialise_db()
            checker = FirdsReportabilityChecker(cache=cache)

            from datetime import date as date_type
            trade_date = date_type.fromisoformat(
                self._trade_date.date().toString("yyyy-MM-dd")
            )
            mic = self.mic.get_value() or None

            result = checker.is_reportable(
                isin=isin, trade_date=trade_date, mic=mic
            )

            # Display in log
            status = "REPORTABLE" if result.is_reportable else "NOT REPORTABLE"
            self.log_viewer.append_line(f"Result:       {status}")
            self.log_viewer.append_line(f"ISIN:         {result.isin}")
            self.log_viewer.append_line(f"Trade date:   {result.trade_date}")
            if hasattr(result, "mic") and result.mic:
                self.log_viewer.append_line(f"MIC:          {result.mic}")
            if hasattr(result, "reason"):
                self.log_viewer.append_line(f"Reason:       {result.reason}")

            # Write to CSV
            out = Path(output_path)
            out.parent.mkdir(parents=True, exist_ok=True)
            with open(out, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow([
                    "isin", "trade_date", "mic",
                    "is_reportable", "reason",
                ])
                writer.writerow([
                    result.isin,
                    str(result.trade_date),
                    getattr(result, "mic", "") or "",
                    "Y" if result.is_reportable else "N",
                    str(getattr(result, "reason", "")),
                ])
            self.log_viewer.append_line(
                f"[GUI] Result written to {output_path}"
            )
        except Exception as e:
            self.log_viewer.append_error(f"[GUI] Error: {e}")
        finally:
            self.run_controls.set_running(False)

    def _on_cancel(self) -> None:
        if self._worker and self._worker.isRunning():
            self._worker.terminate()
            self.log_viewer.append_error("[GUI] Cancelled by user")

    def _on_finished(self, success: bool) -> None:
        self.run_controls.set_running(False)
        if success:
            self.log_viewer.append_line("[GUI] Completed successfully")
        else:
            self.log_viewer.append_error("[GUI] Failed")
        self._worker = None


# ---------------------------------------------------------------------------
# Backfill panel
# ---------------------------------------------------------------------------

class BackfillPanel(QWidget):
    """Panel for the FIRDS backfill script."""

    def __init__(self, api_client: ApiClient, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._client = api_client
        self._worker: Optional[ApiWorker] = None
        pfx = "firds.backfill"

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("<b>FIRDS Backfill</b>"))

        self.config_loader = ConfigLoaderWidget()
        layout.addWidget(self.config_loader)

        self.input_csv = FilePickerWidget(
            "Input CSV:", mode="file", file_filter=CSV_FILTER,
            tooltip="CSV file containing transactions to backfill FIRDS data for.",
            settings_key=f"{pfx}.input_csv",
        )
        layout.addWidget(self.input_csv)

        self.output_csv = FilePickerWidget(
            "Output CSV:", mode="save", file_filter=CSV_FILTER,
            tooltip="Where to write the backfilled output CSV.",
            settings_key=f"{pfx}.output_csv",
        )
        layout.addWidget(self.output_csv)

        self.format = FormFieldWidget(
            "Format:", field_type="dropdown",
            choices=["auto", "incident", "generic"], default="auto",
            tooltip="Input file format detection mode.",
            settings_key=f"{pfx}.format",
        )
        layout.addWidget(self.format)

        self.db_path = FilePickerWidget(
            "Database Path:", mode="file", file_filter=SQLITE_FILTER,
            tooltip="Path to the FIRDS SQLite cache database.\nExample: firds_cache.db",
            settings_key=f"{pfx}.db_path",
        )
        layout.addWidget(self.db_path)

        self.skip_refresh = FormFieldWidget(
            "Skip Refresh", field_type="checkbox",
            tooltip="Skip automatic cache refresh before backfilling.",
            settings_key=f"{pfx}.skip_refresh",
        )
        layout.addWidget(self.skip_refresh)

        self.log_level = FormFieldWidget(
            "Log Level:", field_type="dropdown",
            choices=LOG_LEVELS, default="INFO",
            tooltip="Logging verbosity level.",
            settings_key=f"{pfx}.log_level",
        )
        layout.addWidget(self.log_level)

        self.run_controls = RunControlsWidget()
        self.run_controls.run_clicked.connect(self._on_run)
        self.run_controls.cancel_clicked.connect(self._on_cancel)
        self.run_controls._dry_run_btn.setVisible(False)
        layout.addWidget(self.run_controls)

        self.log_viewer = LogViewerWidget()
        layout.addWidget(self.log_viewer, stretch=1)

    def build_argv(self) -> List[str]:
        argv: List[str] = []

        input_path = self.input_csv.get_path()
        if input_path:
            argv.extend(["--input", input_path])

        output_path = self.output_csv.get_path()
        if output_path:
            argv.extend(["--output", output_path])

        fmt = self.format.get_value()
        if fmt and fmt != "auto":
            argv.extend(["--format", fmt])

        db = self.db_path.get_path()
        if db:
            argv.extend(["--db", db])

        if self.skip_refresh.get_value():
            argv.append("--skip-refresh")

        log_level = self.log_level.get_value()
        if log_level:
            argv.extend(["--log-level", log_level])
        return argv

    def _on_run(self) -> None:
        payload = {
            "inputCsv": self.input_csv.get_path(),
            "outputCsv": self.output_csv.get_path(),
            "format": self.format.get_value(),
            "dbPath": self.db_path.get_path(),
            "skipRefresh": bool(self.skip_refresh.get_value()),
            "config": self.config_loader.get_last_path(),
            "logLevel": self.log_level.get_value(),
        }
        self.log_viewer.clear()
        self.log_viewer.append_line("[GUI] Running: firds-backfill")
        self.run_controls.set_running(True)
        self._worker = ApiWorker("/api/firds/backfill", payload, self._client)
        self._worker.output_line.connect(self.log_viewer.append_line)
        self._worker.finished_signal.connect(self._on_finished)
        self._worker.start()

    def _on_cancel(self) -> None:
        if self._worker and self._worker.isRunning():
            self._worker.terminate()
            self.log_viewer.append_error("[GUI] Cancelled by user")

    def _on_finished(self, success: bool) -> None:
        self.run_controls.set_running(False)
        if success:
            self.log_viewer.append_line("[GUI] Completed successfully")
        else:
            self.log_viewer.append_error("[GUI] Failed")
        self._worker = None


# ---------------------------------------------------------------------------
# Main FIRDS Tab
# ---------------------------------------------------------------------------

class FirdsTab(QWidget):
    """FIRDS Reference Data tab with sidebar navigation."""

    def __init__(self, api_client: ApiClient = None, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._client = api_client or ApiClient()

        layout = QHBoxLayout(self)

        self._sidebar = QListWidget()
        self._sidebar.setFixedWidth(180)
        self._sidebar.currentRowChanged.connect(self._on_sidebar_changed)
        layout.addWidget(self._sidebar)

        self._stack = QStackedWidget()
        layout.addWidget(self._stack, stretch=1)

        panels = [
            ("Cache Refresh", CacheRefreshPanel(self._client)),
            ("Reportability Check", ReportabilityCheckPanel(self._client)),
            ("Backfill", BackfillPanel(self._client)),
        ]

        for label, panel in panels:
            self._sidebar.addItem(label)
            self._stack.addWidget(panel)

        self._sidebar.setCurrentRow(0)

    def _on_sidebar_changed(self, index: int) -> None:
        self._stack.setCurrentIndex(index)

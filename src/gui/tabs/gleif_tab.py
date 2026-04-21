#!/usr/bin/env python3
"""
GLEIF Reference Data Tab
=========================

Three GLEIF reference data script panels:
- Cache Refresh (full + delta modes)
- LEI Check (single LEI, name search, and batch modes)
- Backfill (annotate trade CSVs with LEI data)

Architecture mirrors the FIRDS tab exactly.
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

from gui.constants import LOG_LEVELS, CSV_FILTER, SQLITE_FILTER
from gui.widgets import (
    ConfigLoaderWidget,
    FilePickerWidget,
    FormFieldWidget,
    LogViewerWidget,
    RunControlsWidget,
)
from gui.workers import ScriptRunnerWorker


# ---------------------------------------------------------------------------
# Cache Refresh panel
# ---------------------------------------------------------------------------

class GleifCacheRefreshPanel(QWidget):
    """Panel for the GLEIF cache refresh script."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._worker: Optional[ScriptRunnerWorker] = None
        pfx = "gleif.cache_refresh"

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("<b>GLEIF Cache Refresh</b>"))

        self.config_loader = ConfigLoaderWidget()
        layout.addWidget(self.config_loader)

        self.refresh_type = FormFieldWidget(
            "Refresh Type:", field_type="dropdown",
            choices=["full", "delta"], default="full",
            tooltip="Full refresh downloads the complete GLEIF dataset.\nDelta applies incremental updates.",
            settings_key=f"{pfx}.refresh_type",
        )
        self.refresh_type.value_changed.connect(self._on_type_changed)
        layout.addWidget(self.refresh_type)

        # Delta-specific fields
        self._delta_widget = QWidget()
        delta_layout = QVBoxLayout(self._delta_widget)
        delta_layout.setContentsMargins(0, 0, 0, 0)
        self.delta_type = FormFieldWidget(
            "Delta Window:", field_type="dropdown",
            choices=["8h", "24h", "7d", "31d"], default="24h",
            tooltip="Time window for delta updates.",
            settings_key=f"{pfx}.delta_type",
        )
        delta_layout.addWidget(self.delta_type)
        layout.addWidget(self._delta_widget)
        self._delta_widget.setVisible(False)

        # Full-specific fields
        self.skip_isin_map = FormFieldWidget(
            "Skip ISIN Map", field_type="checkbox",
            tooltip="Skip the ISIN-to-LEI mapping step during refresh.",
            settings_key=f"{pfx}.skip_isin_map",
        )
        layout.addWidget(self.skip_isin_map)

        self.golden_copy_url = FormFieldWidget(
            "Golden Copy URL:", field_type="text",
            tooltip="Override URL for the GLEIF golden copy download.",
            settings_key=f"{pfx}.golden_copy_url",
        )
        layout.addWidget(self.golden_copy_url)

        self.db_path = FilePickerWidget(
            "Database Path:", mode="file", file_filter=SQLITE_FILTER,
            tooltip="Path to the GLEIF SQLite cache database.\nExample: gleif_cache.db",
            settings_key=f"{pfx}.db_path",
        )
        layout.addWidget(self.db_path)

        self.staging_dir = FilePickerWidget(
            "Staging Directory:", mode="directory",
            tooltip="Temporary directory for downloading GLEIF data files.",
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

    def _on_type_changed(self, value: object) -> None:
        """Show delta window dropdown only in delta mode."""
        is_delta = str(value) == "delta"
        self._delta_widget.setVisible(is_delta)
        self.skip_isin_map.setVisible(not is_delta)

    def build_argv(self) -> List[str]:
        rtype = self.refresh_type.get_value()
        argv: List[str] = ["--type", rtype]

        if rtype == "delta":
            argv.extend(["--delta-type", self.delta_type.get_value()])

        if rtype == "full" and self.skip_isin_map.get_value():
            argv.append("--skip-isin-map")

        url = self.golden_copy_url.get_value()
        if url:
            argv.extend(["--golden-copy-url", url])

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
        import importlib
        module = importlib.import_module("src.gleif.scripts.refresh_cache")
        argv = self.build_argv()
        self.log_viewer.clear()
        self.log_viewer.append_line("[GUI] Running: gleif-refresh")
        self.run_controls.set_running(True)
        self._worker = ScriptRunnerWorker(module, argv)
        self._worker.output_line.connect(self.log_viewer.append_line)
        self._worker.error.connect(self.log_viewer.append_error)
        self._worker.finished_signal.connect(self._on_finished)
        self._worker.start()

    def _on_cancel(self) -> None:
        if self._worker and self._worker.isRunning():
            self._worker.terminate()
            self.log_viewer.append_error("[GUI] Cancelled by user")

    def _on_finished(self, exit_code: int) -> None:
        self.run_controls.set_running(False)
        if exit_code == 0:
            self.log_viewer.append_line("[GUI] Completed successfully")
        else:
            self.log_viewer.append_error(f"[GUI] Finished with exit code {exit_code}")
        self._worker = None


# ---------------------------------------------------------------------------
# LEI Check panel (single LEI, name search, and batch modes)
# ---------------------------------------------------------------------------

class LeiCheckPanel(QWidget):
    """Panel for the GLEIF LEI check script.

    Three modes:
    - Single LEI: look up one LEI, display in log or write to file
    - Name Search: search entities by name, display results in log
    - Batch: process CSV files with LEI columns
    """

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._worker: Optional[ScriptRunnerWorker] = None

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("<b>GLEIF LEI Check</b>"))

        self.config_loader = ConfigLoaderWidget()
        layout.addWidget(self.config_loader)

        # Mode selection
        mode_group = QGroupBox("Mode")
        mode_layout = QVBoxLayout(mode_group)
        self._single_radio = QRadioButton("Single LEI Lookup")
        self._name_radio = QRadioButton("Name Search")
        self._batch_radio = QRadioButton("Batch Processing")
        self._single_radio.setChecked(True)
        self._btn_group = QButtonGroup(self)
        self._btn_group.addButton(self._single_radio, 0)
        self._btn_group.addButton(self._name_radio, 1)
        self._btn_group.addButton(self._batch_radio, 2)
        mode_layout.addWidget(self._single_radio)
        mode_layout.addWidget(self._name_radio)
        mode_layout.addWidget(self._batch_radio)
        layout.addWidget(mode_group)

        # --- Single LEI mode fields ---
        self._single_widget = QWidget()
        single_layout = QVBoxLayout(self._single_widget)
        single_layout.setContentsMargins(0, 0, 0, 0)

        self.lei = FormFieldWidget(
            "LEI:", field_type="text",
            tooltip="20-character Legal Entity Identifier",
            settings_key="gleif.lei_check.lei",
        )
        single_layout.addWidget(self.lei)

        date_row = QHBoxLayout()
        date_label = QLabel("Trade Date (optional):")
        date_label.setFixedWidth(140)
        date_row.addWidget(date_label)
        self._trade_date = QDateEdit()
        self._trade_date.setCalendarPopup(True)
        self._trade_date.setDate(QDate.currentDate())
        self._trade_date.setDisplayFormat("yyyy-MM-dd")
        date_row.addWidget(self._trade_date, stretch=1)
        self._use_date = FormFieldWidget(
            "Include trade date", field_type="checkbox",
            tooltip="Include a trade date in the LEI lookup",
        )
        date_row.addWidget(self._use_date)
        single_layout.addLayout(date_row)

        # Output choice for single mode
        single_out_group = QGroupBox("Output")
        single_out_layout = QVBoxLayout(single_out_group)
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
            tooltip="e.g. lei_result.csv",
            settings_key="gleif.lei_check.single_output",
        )
        self.single_output_file.setVisible(False)
        single_out_layout.addWidget(self.single_output_file)
        self._single_out_btn_group.idToggled.connect(
            self._on_single_output_changed
        )
        single_layout.addWidget(single_out_group)

        layout.addWidget(self._single_widget)

        # --- Name search mode fields ---
        self._name_widget = QWidget()
        name_layout = QVBoxLayout(self._name_widget)
        name_layout.setContentsMargins(0, 0, 0, 0)

        self.name_query = FormFieldWidget(
            "Entity Name:", field_type="text",
            tooltip="Entity name to search for in GLEIF database",
            settings_key="gleif.lei_check.name_query",
        )
        name_layout.addWidget(self.name_query)

        self.name_limit = FormFieldWidget(
            "Max Results:", field_type="spinbox", default=20,
            tooltip="Maximum number of results to return",
        )
        name_layout.addWidget(self.name_limit)

        layout.addWidget(self._name_widget)
        self._name_widget.setVisible(False)

        # --- Batch mode fields ---
        self._batch_widget = QWidget()
        batch_layout = QVBoxLayout(self._batch_widget)
        batch_layout.setContentsMargins(0, 0, 0, 0)

        self.input_files = FilePickerWidget(
            "Input CSV:", mode="file", file_filter=CSV_FILTER,
            tooltip="Single CSV file containing LEI column",
            settings_key="gleif.lei_check.input_files",
        )
        batch_layout.addWidget(self.input_files)

        self.input_dir = FilePickerWidget(
            "Input Directory:", mode="directory",
            tooltip="Directory of CSV files to process",
            settings_key="gleif.lei_check.input_dir",
        )
        batch_layout.addWidget(self.input_dir)

        self.glob_pattern = FormFieldWidget(
            "Glob Pattern:", field_type="text", default="*.csv",
            tooltip="File matching pattern for batch input, e.g. *.csv",
            settings_key="gleif.lei_check.glob_pattern",
        )
        batch_layout.addWidget(self.glob_pattern)

        self.output_file = FilePickerWidget(
            "Merged Output CSV:", mode="save", file_filter=CSV_FILTER,
            tooltip="Output CSV with LEI validation results",
            settings_key="gleif.lei_check.output_file",
        )
        batch_layout.addWidget(self.output_file)

        layout.addWidget(self._batch_widget)
        self._batch_widget.setVisible(False)

        # Toggle mode visibility
        self._btn_group.idToggled.connect(self._on_mode_changed)

        # --- Common fields ---
        self.db_path = FilePickerWidget(
            "Database Path:", mode="file", file_filter=SQLITE_FILTER,
            tooltip="GLEIF SQLite cache database file",
            settings_key="gleif.lei_check.db_path",
        )
        layout.addWidget(self.db_path)

        self.log_level = FormFieldWidget(
            "Log Level:", field_type="dropdown",
            choices=LOG_LEVELS, default="WARNING",
            tooltip="Logging verbosity",
            settings_key="gleif.lei_check.log_level",
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
        """Toggle between single, name search, and batch mode fields."""
        if not checked:
            return
        self._single_widget.setVisible(button_id == 0)
        self._name_widget.setVisible(button_id == 1)
        self._batch_widget.setVisible(button_id == 2)

    def _on_single_output_changed(self, button_id: int, checked: bool) -> None:
        """Show/hide the output file picker for single mode."""
        if not checked:
            return
        self.single_output_file.setVisible(button_id == 1)

    def build_argv(self) -> List[str]:
        """Build argv for the gleif-check script."""
        argv: List[str] = []

        if self._single_radio.isChecked():
            lei = self.lei.get_value()
            if lei:
                argv.extend(["--lei", lei])
            if self._use_date.get_value():
                date_str = self._trade_date.date().toString("yyyy-MM-dd")
                argv.extend(["--date", date_str])
        elif self._name_radio.isChecked():
            name = self.name_query.get_value()
            if name:
                argv.extend(["--name", name])
            limit = self.name_limit.get_value()
            if limit and limit != 20:
                argv.extend(["--limit", str(limit)])
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
        """Route to the appropriate execution path."""
        if self._single_radio.isChecked() and self._file_radio.isChecked():
            self._run_single_to_file()
            return

        import importlib
        module = importlib.import_module("src.gleif.scripts.check_lei")
        argv = self.build_argv()
        self.log_viewer.clear()
        self.log_viewer.append_line("[GUI] Running: gleif-check")
        self.run_controls.set_running(True)
        self._worker = ScriptRunnerWorker(module, argv)
        self._worker.output_line.connect(self.log_viewer.append_line)
        self._worker.error.connect(self.log_viewer.append_error)
        self._worker.finished_signal.connect(self._on_finished)
        self._worker.start()

    def _run_single_to_file(self) -> None:
        """Run a single-LEI lookup and write the result to CSV."""
        import csv
        from pathlib import Path

        output_path = self.single_output_file.get_path()
        if not output_path:
            self.log_viewer.append_error(
                "[GUI] No output file selected. Choose a file path first."
            )
            return

        lei = self.lei.get_value()
        if not lei:
            self.log_viewer.append_error("[GUI] LEI is required.")
            return

        self.log_viewer.clear()
        self.log_viewer.append_line(
            f"[GUI] Looking up LEI {lei} and writing to {output_path}"
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

            from gleif.cache import GleifCacheManager
            from gleif.lookup import GleifLookup

            cache = GleifCacheManager(db_path=db_path)
            cache.initialise_db()
            lookup = GleifLookup(cache=cache)

            trade_date = None
            if self._use_date.get_value():
                from datetime import date as date_type
                trade_date = date_type.fromisoformat(
                    self._trade_date.date().toString("yyyy-MM-dd")
                )

            result = lookup.lookup_lei(lei.strip().upper(), trade_date)

            # Display in log
            self.log_viewer.append_line(f"\nLEI Validation Result")
            self.log_viewer.append_line("─" * 40)
            self.log_viewer.append_line(
                f"  LEI              : {result.lei}"
            )
            self.log_viewer.append_line(
                f"  Valid            : {'Yes' if result.is_valid else 'No'}"
            )
            self.log_viewer.append_line(
                f"  Reason           : {result.reason}"
            )
            self.log_viewer.append_line(
                f"  Legal name       : {result.legal_name or '(not found)'}"
            )
            self.log_viewer.append_line(
                f"  Reg. status      : {result.registration_status or '─'}"
            )
            self.log_viewer.append_line(
                f"  Entity status    : {result.entity_status or '─'}"
            )
            self.log_viewer.append_line(
                f"  Entity category  : {result.entity_category or '─'}"
            )
            self.log_viewer.append_line(
                f"  Country          : {result.legal_address_country or '─'}"
            )
            self.log_viewer.append_line(
                f"  Next renewal     : {result.next_renewal_date or '─'}"
            )
            if result.successor_lei:
                self.log_viewer.append_line(
                    f"  Successor LEI    : {result.successor_lei}"
                )
            if trade_date:
                self.log_viewer.append_line(
                    f"  Trade date       : {trade_date}"
                )

            # Write to CSV
            out = Path(output_path)
            out.parent.mkdir(parents=True, exist_ok=True)
            with open(out, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow([
                    "lei", "is_valid", "reason", "legal_name",
                    "registration_status", "entity_status",
                    "entity_category", "legal_address_country",
                    "next_renewal_date", "successor_lei", "trade_date",
                ])
                writer.writerow([
                    result.lei,
                    "Y" if result.is_valid else "N",
                    result.reason,
                    result.legal_name,
                    result.registration_status,
                    result.entity_status,
                    result.entity_category,
                    result.legal_address_country,
                    result.next_renewal_date,
                    result.successor_lei,
                    str(trade_date) if trade_date else "",
                ])
            self.log_viewer.append_line(
                f"\n[GUI] Result written to {output_path}"
            )
        except Exception as e:
            self.log_viewer.append_error(f"[GUI] Error: {e}")
        finally:
            self.run_controls.set_running(False)

    def _on_cancel(self) -> None:
        if self._worker and self._worker.isRunning():
            self._worker.terminate()
            self.log_viewer.append_error("[GUI] Cancelled by user")

    def _on_finished(self, exit_code: int) -> None:
        self.run_controls.set_running(False)
        if exit_code == 0:
            self.log_viewer.append_line("[GUI] Completed successfully")
        else:
            self.log_viewer.append_error(f"[GUI] Finished with exit code {exit_code}")
        self._worker = None


# ---------------------------------------------------------------------------
# Backfill panel
# ---------------------------------------------------------------------------

class GleifBackfillPanel(QWidget):
    """Panel for the GLEIF backfill script."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._worker: Optional[ScriptRunnerWorker] = None

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("<b>GLEIF Backfill</b>"))

        self.config_loader = ConfigLoaderWidget()
        layout.addWidget(self.config_loader)

        self.input_csv = FilePickerWidget(
            "Input CSV:", mode="file", file_filter=CSV_FILTER,
            tooltip="Trade CSV file to annotate with LEI data",
            settings_key="gleif.backfill.input_csv",
        )
        layout.addWidget(self.input_csv)

        self.output_csv = FilePickerWidget(
            "Output CSV:", mode="save", file_filter=CSV_FILTER,
            tooltip="Output CSV with LEI columns added",
            settings_key="gleif.backfill.output_csv",
        )
        layout.addWidget(self.output_csv)

        self.format = FormFieldWidget(
            "Format:", field_type="dropdown",
            choices=["auto", "incident", "generic"], default="auto",
            tooltip="Input format: auto-detect, incident-style, or generic CSV",
            settings_key="gleif.backfill.format",
        )
        layout.addWidget(self.format)

        self.db_path = FilePickerWidget(
            "Database Path:", mode="file", file_filter=SQLITE_FILTER,
            tooltip="GLEIF SQLite cache database file",
            settings_key="gleif.backfill.db_path",
        )
        layout.addWidget(self.db_path)

        self.skip_refresh = FormFieldWidget(
            "Skip Refresh", field_type="checkbox",
            tooltip="Skip refreshing the GLEIF cache before backfill",
            settings_key="gleif.backfill.skip_refresh",
        )
        layout.addWidget(self.skip_refresh)

        self.log_level = FormFieldWidget(
            "Log Level:", field_type="dropdown",
            choices=LOG_LEVELS, default="INFO",
            tooltip="Logging verbosity",
            settings_key="gleif.backfill.log_level",
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
            "logLevel": self.log_level.get_value(),
        }
        self.log_viewer.clear()
        self.log_viewer.append_line("[GUI] Running: gleif-backfill")
        self.run_controls.set_running(True)
        self._worker = ApiWorker(
            client=self._client, endpoint="/api/gleif/backfill", payload=payload
        )
        self._worker.output_line.connect(self.log_viewer.append_line)
        self._worker.finished_signal.connect(self._on_finished)
        self._worker.start()

    def _on_cancel(self) -> None:
        if self._worker and self._worker.isRunning():
            self._worker.terminate()
            self.log_viewer.append_error("[GUI] Cancelled by user")

    def _on_finished(self, exit_code: int) -> None:
        self.run_controls.set_running(False)
        if exit_code == 0:
            self.log_viewer.append_line("[GUI] Completed successfully")
        else:
            self.log_viewer.append_error(f"[GUI] Finished with exit code {exit_code}")
        self._worker = None


# ---------------------------------------------------------------------------
# Main GLEIF Tab
# ---------------------------------------------------------------------------

class GleifTab(QWidget):
    """GLEIF Reference Data tab with sidebar navigation."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)

        layout = QHBoxLayout(self)

        self._sidebar = QListWidget()
        self._sidebar.setFixedWidth(180)
        self._sidebar.currentRowChanged.connect(self._on_sidebar_changed)
        layout.addWidget(self._sidebar)

        self._stack = QStackedWidget()
        layout.addWidget(self._stack, stretch=1)

        panels = [
            ("Cache Refresh", GleifCacheRefreshPanel()),
            ("LEI Check", LeiCheckPanel()),
            ("Backfill", GleifBackfillPanel()),
        ]

        for label, panel in panels:
            self._sidebar.addItem(label)
            self._stack.addWidget(panel)

        self._sidebar.setCurrentRow(0)

    def _on_sidebar_changed(self, index: int) -> None:
        self._stack.setCurrentIndex(index)

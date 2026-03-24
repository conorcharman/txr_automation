#!/usr/bin/env python3
"""
Utilities Tab
=============

Utility script panels:
- XLSX-to-CSV Converter (with conditional mode visibility)
"""

import importlib
from types import ModuleType
from typing import Any, Dict, List, Optional

from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from gui.constants import LOG_LEVELS
from gui.widgets import (
    ConfigLoaderWidget,
    FilePickerWidget,
    FormFieldWidget,
    LogViewerWidget,
    RunControlsWidget,
)
from gui.workers import ScriptRunnerWorker


def _import_script(module_path: str) -> Optional[ModuleType]:
    """Safely import a script module."""
    try:
        return importlib.import_module(module_path)
    except ImportError:
        return None


class XlsxConverterPanel(QWidget):
    """Panel for the XLSX-to-CSV converter script.

    Mode 1 (Recursive) shows parent-dir.
    Mode 2 (Single directory) shows input-dir and output-dir.
    """

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._worker: Optional[ScriptRunnerWorker] = None
        pfx = "utils.xlsx_converter"

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("<b>XLSX to CSV Converter</b>"))

        self.config_loader = ConfigLoaderWidget()
        layout.addWidget(self.config_loader)

        self.mode = FormFieldWidget(
            "Mode:", field_type="dropdown",
            choices=["1 \u2014 Recursive", "2 \u2014 Single directory"],
            default="1 \u2014 Recursive",
            tooltip="Mode 1 recursively converts an entire directory tree.\nMode 2 converts a single directory.",
            settings_key=f"{pfx}.mode",
        )
        self.mode.value_changed.connect(self._on_mode_changed)
        layout.addWidget(self.mode)

        # Mode 1 fields
        self._mode1_widget = QWidget()
        m1_layout = QVBoxLayout(self._mode1_widget)
        m1_layout.setContentsMargins(0, 0, 0, 0)
        self.parent_dir = FilePickerWidget(
            "Parent Directory:", mode="directory",
            tooltip="Top-level directory to recursively search for .xlsx files.",
            settings_key=f"{pfx}.parent_dir",
        )
        m1_layout.addWidget(self.parent_dir)
        layout.addWidget(self._mode1_widget)

        # Mode 2 fields
        self._mode2_widget = QWidget()
        m2_layout = QVBoxLayout(self._mode2_widget)
        m2_layout.setContentsMargins(0, 0, 0, 0)
        self.input_dir = FilePickerWidget(
            "Input Directory:", mode="directory",
            tooltip="Directory containing .xlsx files to convert.",
            settings_key=f"{pfx}.input_dir",
        )
        m2_layout.addWidget(self.input_dir)
        self.output_dir = FilePickerWidget(
            "Output Directory:", mode="directory",
            tooltip="Directory where converted .csv files will be written.",
            settings_key=f"{pfx}.output_dir",
        )
        m2_layout.addWidget(self.output_dir)
        layout.addWidget(self._mode2_widget)
        self._mode2_widget.setVisible(False)

        # Common fields
        self.recursive = FormFieldWidget(
            "Recursive", field_type="checkbox",
            tooltip="Search subdirectories for .xlsx files.",
            settings_key=f"{pfx}.recursive",
        )
        layout.addWidget(self.recursive)

        self.filter_year = FormFieldWidget(
            "Filter Year:", field_type="text",
            tooltip="Only convert files matching this fiscal year.\nExample: 2025",
            placeholder="2025",
            settings_key=f"{pfx}.filter_year",
        )
        layout.addWidget(self.filter_year)

        self.filter_quarter = FormFieldWidget(
            "Filter Quarter:", field_type="text",
            tooltip="Only convert files matching this quarter.\nExample: Q4",
            placeholder="Q4",
            settings_key=f"{pfx}.filter_quarter",
        )
        layout.addWidget(self.filter_quarter)

        self.filter_phases = FormFieldWidget(
            "Filter Phases:", field_type="text",
            tooltip="Space-separated phase numbers to filter.\nExample: 2 3",
            placeholder="2 3",
            settings_key=f"{pfx}.filter_phases",
        )
        layout.addWidget(self.filter_phases)

        self.log_level = FormFieldWidget(
            "Log Level:", field_type="dropdown",
            choices=LOG_LEVELS, default="INFO",
            tooltip="Logging verbosity level.",
            settings_key=f"{pfx}.log_level",
        )
        layout.addWidget(self.log_level)

        self.dry_run = FormFieldWidget(
            "Dry Run", field_type="checkbox",
            tooltip="Preview which files would be converted without writing.",
            settings_key=f"{pfx}.dry_run",
        )
        layout.addWidget(self.dry_run)

        self.force = FormFieldWidget(
            "Force Overwrite", field_type="checkbox",
            tooltip="Overwrite existing CSV files without prompting.",
            settings_key=f"{pfx}.force",
        )
        layout.addWidget(self.force)

        self.run_controls = RunControlsWidget()
        self.run_controls.run_clicked.connect(self._on_run)
        self.run_controls.dry_run_clicked.connect(self._on_dry_run)
        self.run_controls.cancel_clicked.connect(self._on_cancel)
        layout.addWidget(self.run_controls)

        self.log_viewer = LogViewerWidget()
        layout.addWidget(self.log_viewer, stretch=1)

    def _on_mode_changed(self, value: object) -> None:
        """Toggle mode-specific fields."""
        mode_str = str(value)
        is_recursive = mode_str.startswith("1")
        self._mode1_widget.setVisible(is_recursive)
        self._mode2_widget.setVisible(not is_recursive)

    def build_argv(self) -> List[str]:
        argv: List[str] = []
        config_path = self.config_loader.get_last_path()
        if config_path:
            argv.extend(["--config", config_path])

        mode_str = self.mode.get_value()
        mode_num = "1" if mode_str.startswith("1") else "2"
        argv.extend(["--mode", mode_num])

        if mode_num == "1":
            parent = self.parent_dir.get_path()
            if parent:
                argv.extend(["--parent-dir", parent])
        else:
            inp = self.input_dir.get_path()
            if inp:
                argv.extend(["--input-dir", inp])
            out = self.output_dir.get_path()
            if out:
                argv.extend(["--output-dir", out])

        if self.recursive.get_value():
            argv.append("--recursive")

        year = self.filter_year.get_value()
        if year:
            argv.extend(["--filter-year", year])

        quarter = self.filter_quarter.get_value()
        if quarter:
            argv.extend(["--filter-quarter", quarter])

        phases = self.filter_phases.get_value()
        if phases:
            for phase in phases.split():
                argv.extend(["--filter-phase", phase])

        log_level = self.log_level.get_value()
        if log_level:
            argv.extend(["--log-level", log_level])

        if self.dry_run.get_value():
            argv.append("--dry-run")
        if self.force.get_value():
            argv.append("--force")
        return argv

    def _on_run(self) -> None:
        self._execute(dry_run=False)

    def _on_dry_run(self) -> None:
        self._execute(dry_run=True)

    def _execute(self, dry_run: bool = False) -> None:
        module = _import_script("utils.xlsx_csv_converter")
        if module is None:
            self.log_viewer.append_error(
                "Failed to import utils.xlsx_csv_converter"
            )
            return
        argv = self.build_argv()
        if dry_run and "--dry-run" not in argv:
            argv.append("--dry-run")
        self.log_viewer.clear()
        self.log_viewer.append_line(
            f"[GUI] Running: xlsx_csv_converter {' '.join(argv)}"
        )
        self.run_controls.set_running(True)
        self._worker = ScriptRunnerWorker(module, argv)
        self._worker.output_line.connect(self.log_viewer.append_line)
        self._worker.error.connect(self.log_viewer.append_error)
        self._worker.finished_signal.connect(self._on_finished)
        self._worker.start()

    def _on_cancel(self) -> None:
        if self._worker and self._worker.isRunning():
            self._worker.cancel()
            self.log_viewer.append_error("[GUI] Cancelled by user")

    def _on_finished(self, exit_code: int) -> None:
        self.run_controls.set_running(False)
        if exit_code == 0:
            self.log_viewer.append_line("[GUI] Completed successfully")
        else:
            self.log_viewer.append_error(
                f"[GUI] Finished with exit code {exit_code}"
            )
        self._worker = None


class UtilitiesTab(QWidget):
    """Utilities tab with sidebar navigation."""

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
            ("XLSX → CSV", XlsxConverterPanel()),
        ]

        for label, panel in panels:
            self._sidebar.addItem(label)
            self._stack.addWidget(panel)

        self._sidebar.setCurrentRow(0)

    def _on_sidebar_changed(self, index: int) -> None:
        self._stack.setCurrentIndex(index)

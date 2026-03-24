#!/usr/bin/env python3
"""
Accuracy Testing Tab
====================

Tabbed interface for the accuracy testing scripts:
- 9 validation scripts (buyer, seller, inconsistent variants, FTBDM,
  FTSDM, pricing, non-zero-qty, non-zero-amt)
- Run All orchestrator with batch directory + autodiscovery
- 4 utility scripts (SQL extract, template generator, CSV collation,
  data push)

Uses a sidebar list + stacked widget layout with per-panel log viewers.
Panels persist field values across sessions via QSettings caching.
"""

import importlib
import os
from datetime import datetime
from pathlib import Path
from types import ModuleType
from typing import Any, Dict, List, Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from gui.constants import (
    ACCURACY_INCIDENTS,
    CSV_FILTER,
    INCIDENT_CODE_PATTERNS,
    INCIDENT_SCRIPT_MODULES,
    LOG_LEVELS,
    SQL_FILTER,
    YAML_FILTER,
)
from gui.utils.settings import settings
from gui.widgets import (
    ConfigLoaderWidget,
    FilePickerWidget,
    FormFieldWidget,
    IncidentSelectorWidget,
    LogViewerWidget,
    RunControlsWidget,
)
from gui.workers import ScriptRunnerWorker


def _import_script(module_path: str) -> Optional[ModuleType]:
    """Safely import a script module, returning None on failure."""
    try:
        return importlib.import_module(module_path)
    except ImportError:
        return None


def _scrollable(inner: QWidget) -> QScrollArea:
    """Wrap *inner* in a QScrollArea that resizes with its contents."""
    scroll = QScrollArea()
    scroll.setWidget(inner)
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(scroll.Shape.NoFrame)
    return scroll


def _subtitle(text: str) -> QLabel:
    """Create a grey italic subtitle label."""
    lbl = QLabel(text)
    lbl.setStyleSheet("color: grey; font-style: italic; margin-bottom: 4px;")
    return lbl


def _last_run_label() -> QLabel:
    """Create the last-run status indicator label."""
    lbl = QLabel("")
    lbl.setStyleSheet("color: grey; font-size: 11px;")
    return lbl


def _update_last_run(label: QLabel, settings_key: str, success: bool) -> None:
    """Update a last-run label with current timestamp and persist it."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    icon = "\u2713" if success else "\u2717"
    label.setText(f"Last run: {now} {icon}")
    settings.save(f"{settings_key}.last_run_time", now)
    settings.save(f"{settings_key}.last_run_ok", success)


def _restore_last_run(label: QLabel, settings_key: str) -> None:
    """Restore last-run indicator from QSettings."""
    ts = settings.load(f"{settings_key}.last_run_time")
    ok = settings.load(f"{settings_key}.last_run_ok")
    if ts:
        icon = "\u2713" if str(ok).lower() == "true" else "\u2717"
        label.setText(f"Last run: {ts} {icon}")


# ---------------------------------------------------------------------------
# Base panel for validation scripts
# ---------------------------------------------------------------------------

class BaseValidationPanel(QWidget):
    """Base class for ID validation script panels.

    Provides the common form layout shared by all validation scripts:
    config loader, input/output file pickers, log level, dry-run,
    progress checkboxes, run controls, and log viewer.
    """

    def __init__(
        self,
        script_module_path: str,
        title: str,
        subtitle: str = "",
        settings_prefix: str = "",
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._module_path = script_module_path
        self._worker: Optional[ScriptRunnerWorker] = None
        self._settings_prefix = settings_prefix or title.lower().replace(" ", "_")
        pfx = f"accuracy.{self._settings_prefix}"

        inner = QWidget()
        layout = QVBoxLayout(inner)
        layout.addWidget(QLabel(f"<b>{title}</b>"))
        if subtitle:
            layout.addWidget(_subtitle(subtitle))

        self._last_run = _last_run_label()
        _restore_last_run(self._last_run, pfx)
        layout.addWidget(self._last_run)

        # Config loader
        self.config_loader = ConfigLoaderWidget()
        self.config_loader.config_loaded.connect(self.populate_from_config)
        layout.addWidget(self.config_loader)

        # File fields
        self.input_file = FilePickerWidget(
            "Input transactions CSV:",
            mode="file",
            tooltip="The raw transactions CSV file to validate.\nExample: 7_5_buyer_transactions.csv",
            settings_key=f"{pfx}.input_file",
        )
        layout.addWidget(self.input_file)

        self.output_file = FilePickerWidget(
            "Output results CSV:",
            mode="save",
            tooltip="Where to write the validation results CSV.\nExample: 7_5_buyer_results.csv",
            settings_key=f"{pfx}.output_file",
        )
        layout.addWidget(self.output_file)

        # Options
        self.log_level = FormFieldWidget(
            "Log Level:", field_type="dropdown",
            choices=LOG_LEVELS, default="INFO",
            tooltip="Logging verbosity level.",
            settings_key=f"{pfx}.log_level",
        )
        layout.addWidget(self.log_level)

        self.dry_run = FormFieldWidget(
            "Dry Run", field_type="checkbox",
            tooltip="Simulate the run without writing output files.",
            settings_key=f"{pfx}.dry_run",
        )
        layout.addWidget(self.dry_run)

        self.progress = FormFieldWidget(
            "Progress Bar", field_type="checkbox",
            tooltip="Show a progress bar during processing.",
            settings_key=f"{pfx}.progress",
        )
        layout.addWidget(self.progress)

        # Run controls
        self.run_controls = RunControlsWidget()
        self.run_controls.run_clicked.connect(self._on_run)
        self.run_controls.dry_run_clicked.connect(self._on_dry_run)
        self.run_controls.cancel_clicked.connect(self._on_cancel)
        layout.addWidget(self.run_controls)

        # Log viewer
        self.log_viewer = LogViewerWidget()
        layout.addWidget(self.log_viewer, stretch=1)

        # Wrap in scroll area
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(_scrollable(inner))

    def build_argv(self) -> List[str]:
        """Build sys.argv from current form state."""
        argv: List[str] = ["--gui-mode"]
        config_path = self.config_loader.get_last_path()
        if config_path:
            argv.extend(["--config", config_path])
        else:
            input_path = self.input_file.get_path()
            output_path = self.output_file.get_path()
            if input_path:
                argv.append(input_path)
            if output_path:
                argv.append(output_path)

        log_level = self.log_level.get_value()
        if log_level:
            argv.extend(["--log-level", log_level])
        if self.dry_run.get_value():
            argv.append("--dry-run")
        if self.progress.get_value():
            argv.append("--progress")
        return argv

    def populate_from_config(self, config: Dict[str, Any]) -> None:
        """Fill form fields from parsed YAML config dict."""
        paths = config.get("paths", {})
        processor = config.get("processor", {})
        self.input_file.set_path(paths.get("input_file", ""))
        self.output_file.set_path(paths.get("output_file", ""))
        self.log_level.set_value(processor.get("log_level", "INFO"))

    def _on_run(self) -> None:
        self._execute(dry_run=False)

    def _on_dry_run(self) -> None:
        self._execute(dry_run=True)

    def _execute(self, dry_run: bool = False) -> None:
        """Import the script module and run main() in a worker thread."""
        module = _import_script(self._module_path)
        if module is None:
            self.log_viewer.append_error(
                f"Failed to import {self._module_path}"
            )
            return

        argv = self.build_argv()
        if dry_run and "--dry-run" not in argv:
            argv.append("--dry-run")

        self.log_viewer.clear()
        self.log_viewer.append_line(
            f"[GUI] Running: {self._module_path} {' '.join(argv)}"
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
        pfx = f"accuracy.{self._settings_prefix}"
        if exit_code == 0:
            self.log_viewer.append_line("[GUI] Completed successfully")
            _update_last_run(self._last_run, pfx, True)
        else:
            self.log_viewer.append_error(
                f"[GUI] Finished with exit code {exit_code}"
            )
            _update_last_run(self._last_run, pfx, False)
        self._worker = None


# ---------------------------------------------------------------------------
# FTBDM / FTSDM panels (extra fields for LEI data)
# ---------------------------------------------------------------------------

class DecisionMakerPanel(BaseValidationPanel):
    """Panel for FTBDM/FTSDM validation scripts with extra file fields."""

    def __init__(
        self,
        script_module_path: str,
        title: str,
        subtitle: str = "",
        settings_prefix: str = "",
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(
            script_module_path, title,
            subtitle=subtitle,
            settings_prefix=settings_prefix,
            parent=parent,
        )
        pfx = f"accuracy.{self._settings_prefix}"

        # Find the inner layout (inside the scroll area)
        scroll_area = self.findChild(QScrollArea)
        assert scroll_area is not None
        inner = scroll_area.widget()
        assert inner is not None
        layout: QVBoxLayout = inner.layout()  # type: ignore[assignment]

        # Insert extra fields before log level
        idx = layout.indexOf(self.log_level)

        self.lei_data_file = FilePickerWidget(
            "LEI reference data CSV:",
            mode="file", file_filter=CSV_FILTER,
            tooltip="LEI reference data for decision maker lookups.\nExample: lei_data_2025.csv",
            settings_key=f"{pfx}.lei_data_file",
        )
        layout.insertWidget(idx, self.lei_data_file)

        self.id_formats_file = FilePickerWidget(
            "ID format definitions CSV:",
            mode="file", file_filter=CSV_FILTER,
            tooltip="CSV defining valid ID formats per country.\nExample: id_formats.csv",
            settings_key=f"{pfx}.id_formats_file",
        )
        layout.insertWidget(idx + 1, self.id_formats_file)

        # Add verbose checkbox after dry_run
        self.verbose = FormFieldWidget(
            "Verbose", field_type="checkbox",
            tooltip="Enable verbose output for debugging.",
            settings_key=f"{pfx}.verbose",
        )
        dry_run_idx = layout.indexOf(self.dry_run)
        layout.insertWidget(dry_run_idx + 1, self.verbose)

    def build_argv(self) -> List[str]:
        """Build argv with extra decision-maker fields."""
        argv: List[str] = ["--gui-mode"]
        config_path = self.config_loader.get_last_path()
        if config_path:
            argv.extend(["--config", config_path])
        else:
            input_path = self.input_file.get_path()
            output_path = self.output_file.get_path()
            if input_path:
                argv.extend(["--input", input_path])
            if output_path:
                argv.extend(["--output", output_path])

        lei_path = self.lei_data_file.get_path()
        if lei_path:
            argv.extend(["--lei-data", lei_path])

        id_fmt_path = self.id_formats_file.get_path()
        if id_fmt_path:
            argv.extend(["--id-formats", id_fmt_path])

        log_level = self.log_level.get_value()
        if log_level:
            argv.extend(["--log-level", log_level])
        if self.dry_run.get_value():
            argv.append("--dry-run")
        if self.verbose.get_value():
            argv.append("--verbose")
        return argv


# ---------------------------------------------------------------------------
# Run All Validations panel — with batch directory + autodiscovery
# ---------------------------------------------------------------------------

class RunAllPanel(QWidget):
    """Panel for the run-all-validations orchestrator.

    Supports two modes:
    - Config mode: delegates to run_all_validations.py with a YAML config
    - Batch directory mode: discovers input CSVs from a base directory and
      runs each selected validation individually
    """

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._worker: Optional[ScriptRunnerWorker] = None
        self._run_queue: List[Dict[str, str]] = []
        pfx = "accuracy.run_all"

        inner = QWidget()
        layout = QVBoxLayout(inner)
        layout.addWidget(QLabel("<b>Run All Validations</b>"))
        layout.addWidget(_subtitle(
            "Run multiple validation scripts in sequence with shared settings"
        ))

        self._last_run = _last_run_label()
        _restore_last_run(self._last_run, pfx)
        layout.addWidget(self._last_run)

        # Config loader
        self.config_loader = ConfigLoaderWidget()
        layout.addWidget(self.config_loader)

        # --- Batch directory section ---
        batch_group = QGroupBox("Batch Directory (optional)")
        batch_layout = QVBoxLayout(batch_group)
        batch_layout.addWidget(QLabel(
            "Set base directories to autodiscover input files by incident code."
        ))

        self.base_input_dir = FilePickerWidget(
            "Base input directory:",
            mode="directory",
            tooltip="Root folder containing per-incident input CSVs.\nFiles are matched by incident code (e.g. 7_5, 7_37).",
            settings_key=f"{pfx}.base_input_dir",
        )
        batch_layout.addWidget(self.base_input_dir)

        self.base_output_dir = FilePickerWidget(
            "Base output directory:",
            mode="directory",
            tooltip="Root folder where per-incident output CSVs will be written.",
            settings_key=f"{pfx}.base_output_dir",
        )
        batch_layout.addWidget(self.base_output_dir)

        discover_row = QHBoxLayout()
        self._discover_btn = QPushButton("Discover Files")
        self._discover_btn.setFixedWidth(120)
        self._discover_btn.clicked.connect(self._on_discover)
        discover_row.addWidget(self._discover_btn)
        self._discover_status = QLabel("")
        self._discover_status.setStyleSheet("color: grey; font-size: 11px;")
        discover_row.addWidget(self._discover_status, stretch=1)
        batch_layout.addLayout(discover_row)

        self._discovery_results = QLabel("")
        self._discovery_results.setWordWrap(True)
        self._discovery_results.setStyleSheet("font-size: 11px;")
        batch_layout.addWidget(self._discovery_results)

        layout.addWidget(batch_group)

        # --- Incident selector ---
        self.incident_selector = IncidentSelectorWidget(
            ACCURACY_INCIDENTS,
            settings_key=f"{pfx}.selected_incidents",
        )
        layout.addWidget(self.incident_selector)

        # --- Options ---
        options_group = QGroupBox("Options")
        options_layout = QVBoxLayout(options_group)

        self.log_level = FormFieldWidget(
            "Log Level:", field_type="dropdown",
            choices=LOG_LEVELS, default="INFO",
            tooltip="Logging verbosity level.",
            settings_key=f"{pfx}.log_level",
        )
        options_layout.addWidget(self.log_level)

        self.stop_on_error = FormFieldWidget(
            "Stop on Error", field_type="checkbox",
            tooltip="Stop the batch if any validation script fails.",
            settings_key=f"{pfx}.stop_on_error",
        )
        options_layout.addWidget(self.stop_on_error)

        self.verbose = FormFieldWidget(
            "Verbose", field_type="checkbox",
            tooltip="Enable verbose output.",
            settings_key=f"{pfx}.verbose",
        )
        options_layout.addWidget(self.verbose)

        self.list_only = FormFieldWidget(
            "List Only", field_type="checkbox",
            tooltip="List validations that would run without executing them.",
            settings_key=f"{pfx}.list_only",
        )
        options_layout.addWidget(self.list_only)

        self.dry_run = FormFieldWidget(
            "Dry Run", field_type="checkbox",
            tooltip="Simulate the run without writing output files.",
            settings_key=f"{pfx}.dry_run",
        )
        options_layout.addWidget(self.dry_run)

        self.progress = FormFieldWidget(
            "Progress Bar", field_type="checkbox",
            tooltip="Show a progress bar during processing.",
            settings_key=f"{pfx}.progress",
        )
        options_layout.addWidget(self.progress)

        layout.addWidget(options_group)

        # Run controls
        self.run_controls = RunControlsWidget()
        self.run_controls.run_clicked.connect(self._on_run)
        self.run_controls.dry_run_clicked.connect(self._on_dry_run)
        self.run_controls.cancel_clicked.connect(self._on_cancel)
        layout.addWidget(self.run_controls)

        # Log viewer
        self.log_viewer = LogViewerWidget()
        layout.addWidget(self.log_viewer, stretch=1)

        # Wrap in scroll area
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(_scrollable(inner))

        # Internal state for autodiscovery
        self._discovered_files: Dict[str, str] = {}

    # ---- Autodiscovery ----

    def _on_discover(self) -> None:
        """Scan base input directory for files matching incident codes."""
        base_dir = self.base_input_dir.get_path()
        if not base_dir or not os.path.isdir(base_dir):
            self._discover_status.setText("Please select a valid base input directory.")
            return

        selected = self.incident_selector.get_selected()
        if not selected:
            self._discover_status.setText("No incidents selected.")
            return

        self._discovered_files.clear()
        results_lines: List[str] = []
        files_in_dir = os.listdir(base_dir)

        for name in selected:
            patterns = INCIDENT_CODE_PATTERNS.get(name, [])
            matched = ""
            for fname in files_in_dir:
                lower = fname.lower()
                if not lower.endswith(".csv"):
                    continue
                for pattern in patterns:
                    if pattern in fname:
                        matched = os.path.join(base_dir, fname)
                        break
                if matched:
                    break

            if matched:
                self._discovered_files[name] = matched
                results_lines.append(
                    f'<span style="color:green;">\u2713 {name}: {os.path.basename(matched)}</span>'
                )
            else:
                results_lines.append(
                    f'<span style="color:orange;">\u2717 {name}: not found</span>'
                )

        found = len(self._discovered_files)
        total = len(selected)
        self._discover_status.setText(f"Discovered {found}/{total} files.")
        self._discovery_results.setText("<br>".join(results_lines))

    # ---- Execution ----

    def _on_run(self) -> None:
        self._execute(dry_run=False)

    def _on_dry_run(self) -> None:
        self._execute(dry_run=True)

    def _execute(self, dry_run: bool = False) -> None:
        """Run validations — batch mode if base dirs set, else config mode."""
        base_in = self.base_input_dir.get_path()
        base_out = self.base_output_dir.get_path()

        if base_in and base_out and self._discovered_files:
            self._execute_batch(dry_run)
        else:
            self._execute_config(dry_run)

    def _execute_config(self, dry_run: bool = False) -> None:
        """Delegate to run_all_validations.py with a config file."""
        module = _import_script("accuracy_testing.scripts.run_all_validations")
        if module is None:
            self.log_viewer.append_error(
                "Failed to import run_all_validations"
            )
            return

        argv = self._build_config_argv()
        if dry_run and "--dry-run" not in argv:
            argv.append("--dry-run")

        selected = self.incident_selector.get_selected()
        if selected:
            argv.extend(["--validations"] + selected)

        self.log_viewer.clear()
        self.log_viewer.append_line(
            f"[GUI] Running: run_all_validations {' '.join(argv)}"
        )
        self.run_controls.set_running(True)

        self._worker = ScriptRunnerWorker(module, argv)
        self._worker.output_line.connect(self.log_viewer.append_line)
        self._worker.error.connect(self.log_viewer.append_error)
        self._worker.finished_signal.connect(self._on_finished)
        self._worker.start()

    def _build_config_argv(self) -> List[str]:
        argv: List[str] = ["--gui-mode"]
        config_path = self.config_loader.get_last_path()
        if config_path:
            argv.extend(["--config", config_path])
        log_level = self.log_level.get_value()
        if log_level:
            argv.extend(["--log-level", log_level])
        if self.stop_on_error.get_value():
            argv.append("--stop-on-error")
        if self.verbose.get_value():
            argv.append("--verbose")
        if self.list_only.get_value():
            argv.append("--list")
        return argv

    def _execute_batch(self, dry_run: bool = False) -> None:
        """Run each discovered script one at a time in sequence."""
        base_out = self.base_output_dir.get_path()
        selected = self.incident_selector.get_selected()

        self._run_queue = []
        for name in selected:
            input_path = self._discovered_files.get(name)
            if not input_path:
                continue
            module_path = INCIDENT_SCRIPT_MODULES.get(name)
            if not module_path:
                continue
            output_name = f"{Path(input_path).stem}_results.csv"
            output_path = os.path.join(base_out, output_name)
            self._run_queue.append({
                "name": name,
                "module": module_path,
                "input": input_path,
                "output": output_path,
                "dry_run": str(dry_run),
            })

        if not self._run_queue:
            self.log_viewer.append_error(
                "[GUI] No matching files discovered for selected incidents."
            )
            return

        self.log_viewer.clear()
        self.log_viewer.append_line(
            f"[GUI] Batch mode: running {len(self._run_queue)} validation(s) sequentially"
        )
        self.run_controls.set_running(True)
        self._run_next_in_queue()

    def _run_next_in_queue(self) -> None:
        """Pop the next job from the queue and run it."""
        if not self._run_queue:
            self.run_controls.set_running(False)
            self.log_viewer.append_line("[GUI] Batch complete.")
            pfx = "accuracy.run_all"
            _update_last_run(self._last_run, pfx, True)
            return

        job = self._run_queue.pop(0)
        module_path = job["module"]
        module = _import_script(module_path)
        if module is None:
            self.log_viewer.append_error(
                f"[GUI] Failed to import {module_path}, skipping."
            )
            self._run_next_in_queue()
            return

        argv = ["--gui-mode", job["input"], job["output"]]
        log_level = self.log_level.get_value()
        if log_level:
            argv.extend(["--log-level", log_level])
        if job.get("dry_run") == "True":
            argv.append("--dry-run")
        if self.progress.get_value():
            argv.append("--progress")

        self.log_viewer.append_line(
            f"\n[GUI] === {job['name']} ===\n"
            f"[GUI] Running: {module_path} {' '.join(argv)}"
        )

        self._worker = ScriptRunnerWorker(module, argv)
        self._worker.output_line.connect(self.log_viewer.append_line)
        self._worker.error.connect(self.log_viewer.append_error)
        self._worker.finished_signal.connect(self._on_batch_step_finished)
        self._worker.start()

    def _on_batch_step_finished(self, exit_code: int) -> None:
        """Handle completion of one batch step."""
        if exit_code == 0:
            self.log_viewer.append_line("[GUI] Step completed successfully")
        else:
            self.log_viewer.append_error(
                f"[GUI] Step finished with exit code {exit_code}"
            )
            if self.stop_on_error.get_value():
                self._run_queue.clear()
                self.run_controls.set_running(False)
                self.log_viewer.append_error(
                    "[GUI] Batch stopped due to error."
                )
                pfx = "accuracy.run_all"
                _update_last_run(self._last_run, pfx, False)
                return
        self._worker = None
        self._run_next_in_queue()

    def _on_cancel(self) -> None:
        self._run_queue.clear()
        if self._worker and self._worker.isRunning():
            self._worker.cancel()
            self.log_viewer.append_error("[GUI] Cancelled by user")
        self.run_controls.set_running(False)

    def _on_finished(self, exit_code: int) -> None:
        """Handle completion for config mode."""
        self.run_controls.set_running(False)
        pfx = "accuracy.run_all"
        if exit_code == 0:
            self.log_viewer.append_line("[GUI] Completed successfully")
            _update_last_run(self._last_run, pfx, True)
        else:
            self.log_viewer.append_error(
                f"[GUI] Finished with exit code {exit_code}"
            )
            _update_last_run(self._last_run, pfx, False)
        self._worker = None


# ---------------------------------------------------------------------------
# SQL Extract Generator panel — single file + batch directory modes
# ---------------------------------------------------------------------------

class SQLExtractPanel(QWidget):
    """Panel for the SQL extract generator script."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._worker: Optional[ScriptRunnerWorker] = None
        self._batch_queue: List[Dict[str, str]] = []
        pfx = "accuracy.sql_extract"

        inner = QWidget()
        layout = QVBoxLayout(inner)
        layout.addWidget(QLabel("<b>SQL Extract Generator</b>"))
        layout.addWidget(_subtitle(
            "Generate batched SQL extract files from a template and input CSV of IDs"
        ))

        self._last_run = _last_run_label()
        _restore_last_run(self._last_run, pfx)
        layout.addWidget(self._last_run)

        self.config_loader = ConfigLoaderWidget()
        self.config_loader.config_loaded.connect(self.populate_from_config)
        layout.addWidget(self.config_loader)

        # --- Mode selector ---
        mode_row = QHBoxLayout()
        mode_row.addWidget(QLabel("Mode:"))
        self._single_radio = QRadioButton("Single file")
        self._batch_radio = QRadioButton("Batch directory")
        self._single_radio.setChecked(True)
        self._single_radio.toggled.connect(self._on_mode_changed)
        mode_row.addWidget(self._single_radio)
        mode_row.addWidget(self._batch_radio)
        mode_row.addStretch()
        layout.addLayout(mode_row)

        # --- Single-file fields ---
        self._single_group = QGroupBox("Input Files")
        single_layout = QVBoxLayout(self._single_group)

        self.sql_template = FilePickerWidget(
            "SQL template file:",
            mode="file", file_filter=SQL_FILTER,
            tooltip="The SQL template with a placeholder token to fill.\nExample: 7_5_extract_template.sql",
            settings_key=f"{pfx}.sql_template",
        )
        single_layout.addWidget(self.sql_template)

        self.input_csv = FilePickerWidget(
            "Input IDs CSV:",
            mode="file",
            tooltip="CSV containing the IDs to splice into the SQL template.\nExample: 7_5_ids.csv",
            settings_key=f"{pfx}.input_csv",
        )
        single_layout.addWidget(self.input_csv)

        layout.addWidget(self._single_group)

        # --- Batch directory fields ---
        self._batch_group = QGroupBox("Batch Directories")
        batch_layout = QVBoxLayout(self._batch_group)

        self.templates_dir = FilePickerWidget(
            "SQL templates directory:",
            mode="directory",
            tooltip="Directory containing .sql template files.\nAll .sql files will be listed.",
            settings_key=f"{pfx}.templates_dir",
        )
        batch_layout.addWidget(self.templates_dir)

        self.input_csvs_dir = FilePickerWidget(
            "Input CSVs directory:",
            mode="directory",
            tooltip="Directory containing input .csv files.\nAll .csv files will be listed.",
            settings_key=f"{pfx}.input_csvs_dir",
        )
        batch_layout.addWidget(self.input_csvs_dir)

        discover_row = QHBoxLayout()
        self._batch_discover_btn = QPushButton("Discover Files")
        self._batch_discover_btn.setFixedWidth(120)
        self._batch_discover_btn.clicked.connect(self._on_batch_discover)
        discover_row.addWidget(self._batch_discover_btn)
        self._batch_discover_status = QLabel("")
        self._batch_discover_status.setStyleSheet("color: grey; font-size: 11px;")
        discover_row.addWidget(self._batch_discover_status, stretch=1)
        batch_layout.addLayout(discover_row)

        self._sql_file_list = QListWidget()
        self._sql_file_list.setMaximumHeight(120)
        batch_layout.addWidget(QLabel("Discovered SQL templates:"))
        batch_layout.addWidget(self._sql_file_list)

        self._csv_file_list = QListWidget()
        self._csv_file_list.setMaximumHeight(120)
        batch_layout.addWidget(QLabel("Discovered CSV files:"))
        batch_layout.addWidget(self._csv_file_list)

        layout.addWidget(self._batch_group)
        self._batch_group.setVisible(False)

        # --- Shared fields ---
        shared_group = QGroupBox("Output & Parameters")
        shared_layout = QVBoxLayout(shared_group)

        self.output_dir = FilePickerWidget(
            "Output directory:",
            mode="directory",
            tooltip="Directory where generated SQL/DTF files will be saved.",
            settings_key=f"{pfx}.output_dir",
        )
        shared_layout.addWidget(self.output_dir)

        self.batch_size = FormFieldWidget(
            "Batch size:", field_type="spinbox", default=900,
            tooltip="Number of IDs per SQL batch.\nExample: 900",
            settings_key=f"{pfx}.batch_size",
        )
        shared_layout.addWidget(self.batch_size)

        self.placeholder = FormFieldWidget(
            "SQL placeholder token:", field_type="text",
            tooltip="The placeholder string in the template to replace with IDs.\nExample: {PLACEHOLDER}",
            placeholder="{PLACEHOLDER}",
            settings_key=f"{pfx}.placeholder",
        )
        shared_layout.addWidget(self.placeholder)

        self.column = FormFieldWidget(
            "ID column name:", field_type="text",
            tooltip="Name of the CSV column containing IDs.\nExample: TransactionRef",
            placeholder="TransactionRef",
            settings_key=f"{pfx}.column",
        )
        shared_layout.addWidget(self.column)

        self.output_format = FormFieldWidget(
            "Output format:", field_type="dropdown",
            choices=["sql", "dtf", "both"], default="both",
            tooltip="Output file format: SQL only, DTF only, or both.",
            settings_key=f"{pfx}.output_format",
        )
        shared_layout.addWidget(self.output_format)

        self.incident_code = FormFieldWidget(
            "Incident batch code:", field_type="text",
            tooltip="Short code used for labelling output files.\nExample: 7_5",
            placeholder="7_5",
            settings_key=f"{pfx}.incident_code",
        )
        shared_layout.addWidget(self.incident_code)

        self.dtf_template = FilePickerWidget(
            "DTF template file:",
            mode="file",
            tooltip="Optional DTF template file for DTF output mode.\nExample: dtf_template.csv",
            settings_key=f"{pfx}.dtf_template",
        )
        shared_layout.addWidget(self.dtf_template)

        layout.addWidget(shared_group)

        # --- Options ---
        self.dry_run = FormFieldWidget(
            "Dry Run", field_type="checkbox",
            tooltip="Simulate the run without writing output files.",
            settings_key=f"{pfx}.dry_run",
        )
        layout.addWidget(self.dry_run)

        self.verbose = FormFieldWidget(
            "Verbose", field_type="checkbox",
            tooltip="Enable verbose output.",
            settings_key=f"{pfx}.verbose",
        )
        layout.addWidget(self.verbose)

        self.run_controls = RunControlsWidget()
        self.run_controls.run_clicked.connect(self._on_run)
        self.run_controls.dry_run_clicked.connect(self._on_dry_run)
        self.run_controls.cancel_clicked.connect(self._on_cancel)
        layout.addWidget(self.run_controls)

        self.log_viewer = LogViewerWidget()
        layout.addWidget(self.log_viewer, stretch=1)

        # Wrap in scroll area
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(_scrollable(inner))

    # ---- Mode toggle ----

    def _on_mode_changed(self, single_checked: bool) -> None:
        self._single_group.setVisible(single_checked)
        self._batch_group.setVisible(not single_checked)

    # ---- Batch discover ----

    def _on_batch_discover(self) -> None:
        """Populate the SQL and CSV file lists from their directories."""
        self._sql_file_list.clear()
        self._csv_file_list.clear()

        sql_dir = self.templates_dir.get_path()
        csv_dir = self.input_csvs_dir.get_path()

        sql_count = 0
        if sql_dir and os.path.isdir(sql_dir):
            for fname in sorted(os.listdir(sql_dir)):
                if fname.lower().endswith(".sql"):
                    item = QListWidgetItem(fname)
                    item.setData(Qt.ItemDataRole.UserRole, os.path.join(sql_dir, fname))
                    item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                    item.setCheckState(Qt.CheckState.Checked)
                    self._sql_file_list.addItem(item)
                    sql_count += 1

        csv_count = 0
        if csv_dir and os.path.isdir(csv_dir):
            for fname in sorted(os.listdir(csv_dir)):
                if fname.lower().endswith(".csv"):
                    item = QListWidgetItem(fname)
                    item.setData(Qt.ItemDataRole.UserRole, os.path.join(csv_dir, fname))
                    item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                    item.setCheckState(Qt.CheckState.Checked)
                    self._csv_file_list.addItem(item)
                    csv_count += 1

        self._batch_discover_status.setText(
            f"Found {sql_count} SQL template(s), {csv_count} CSV file(s)."
        )

    # ---- Build argv ----

    def build_argv(self) -> List[str]:
        """Build argv for a single-file run."""
        argv: List[str] = ["--gui-mode"]
        config_path = self.config_loader.get_last_path()
        if config_path:
            argv.extend(["--config", config_path])

        template = self.sql_template.get_path()
        if template:
            argv.extend(["--template", template])

        input_path = self.input_csv.get_path()
        if input_path:
            argv.extend(["--input", input_path])

        output_dir = self.output_dir.get_path()
        if output_dir:
            argv.extend(["--output", output_dir])

        batch_size = self.batch_size.get_value()
        if batch_size and batch_size != 900:
            argv.extend(["--batch-size", str(batch_size)])

        placeholder = self.placeholder.get_value()
        if placeholder:
            argv.extend(["--placeholder", placeholder])

        col = self.column.get_value()
        if col:
            argv.extend(["--column", col])

        fmt = self.output_format.get_value()
        if fmt and fmt != "both":
            argv.extend(["--output-format", fmt])

        incident = self.incident_code.get_value()
        if incident:
            argv.extend(["--incident-code", incident])

        dtf = self.dtf_template.get_path()
        if dtf:
            argv.extend(["--dtf-template", dtf])

        if self.dry_run.get_value():
            argv.append("--dry-run")
        if self.verbose.get_value():
            argv.append("--verbose")
        return argv

    def populate_from_config(self, config: Dict[str, Any]) -> None:
        paths = config.get("paths", {})
        self.input_csv.set_path(paths.get("input_file", ""))
        self.output_dir.set_path(paths.get("output_dir", ""))
        self.sql_template.set_path(paths.get("sql_template", ""))

    # ---- Execution ----

    def _on_run(self) -> None:
        if self._batch_radio.isChecked():
            self._execute_batch(dry_run=False)
        else:
            self._execute_single(dry_run=False)

    def _on_dry_run(self) -> None:
        if self._batch_radio.isChecked():
            self._execute_batch(dry_run=True)
        else:
            self._execute_single(dry_run=True)

    def _execute_single(self, dry_run: bool = False) -> None:
        module = _import_script(
            "accuracy_testing.scripts.sql_extract_generator"
        )
        if module is None:
            self.log_viewer.append_error(
                "Failed to import sql_extract_generator"
            )
            return
        argv = self.build_argv()
        if dry_run and "--dry-run" not in argv:
            argv.append("--dry-run")
        self.log_viewer.clear()
        self.log_viewer.append_line(
            f"[GUI] Running: sql_extract_generator {' '.join(argv)}"
        )
        self.run_controls.set_running(True)
        self._worker = ScriptRunnerWorker(module, argv)
        self._worker.output_line.connect(self.log_viewer.append_line)
        self._worker.error.connect(self.log_viewer.append_error)
        self._worker.finished_signal.connect(self._on_finished)
        self._worker.start()

    def _execute_batch(self, dry_run: bool = False) -> None:
        """Run sql_extract_generator for each checked SQL+CSV pair."""
        checked_sql = self._get_checked_items(self._sql_file_list)
        checked_csv = self._get_checked_items(self._csv_file_list)

        if not checked_sql or not checked_csv:
            self.log_viewer.append_error(
                "[GUI] Select at least one SQL template and one CSV file."
            )
            return

        self._batch_queue = []
        for sql_path in checked_sql:
            for csv_path in checked_csv:
                self._batch_queue.append({
                    "template": sql_path,
                    "input": csv_path,
                    "dry_run": str(dry_run),
                })

        self.log_viewer.clear()
        self.log_viewer.append_line(
            f"[GUI] Batch mode: {len(self._batch_queue)} run(s) "
            f"({len(checked_sql)} template(s) x {len(checked_csv)} CSV(s))"
        )
        self.run_controls.set_running(True)
        self._run_next_batch()

    def _get_checked_items(self, list_widget: QListWidget) -> List[str]:
        paths: List[str] = []
        for i in range(list_widget.count()):
            item = list_widget.item(i)
            if item.checkState() == Qt.CheckState.Checked:
                paths.append(item.data(Qt.ItemDataRole.UserRole))
        return paths

    def _run_next_batch(self) -> None:
        if not self._batch_queue:
            self.run_controls.set_running(False)
            self.log_viewer.append_line("[GUI] Batch complete.")
            _update_last_run(self._last_run, "accuracy.sql_extract", True)
            return

        job = self._batch_queue.pop(0)
        module = _import_script(
            "accuracy_testing.scripts.sql_extract_generator"
        )
        if module is None:
            self.log_viewer.append_error(
                "Failed to import sql_extract_generator, skipping."
            )
            self._run_next_batch()
            return

        argv: List[str] = ["--gui-mode"]
        argv.extend(["--template", job["template"]])
        argv.extend(["--input", job["input"]])

        output_dir = self.output_dir.get_path()
        if output_dir:
            argv.extend(["--output", output_dir])

        batch_size = self.batch_size.get_value()
        if batch_size and batch_size != 900:
            argv.extend(["--batch-size", str(batch_size)])

        placeholder = self.placeholder.get_value()
        if placeholder:
            argv.extend(["--placeholder", placeholder])

        col = self.column.get_value()
        if col:
            argv.extend(["--column", col])

        fmt = self.output_format.get_value()
        if fmt and fmt != "both":
            argv.extend(["--output-format", fmt])

        if job.get("dry_run") == "True":
            argv.append("--dry-run")
        if self.verbose.get_value():
            argv.append("--verbose")

        self.log_viewer.append_line(
            f"\n[GUI] === {Path(job['template']).name} + "
            f"{Path(job['input']).name} ===\n"
            f"[GUI] Running: sql_extract_generator {' '.join(argv)}"
        )

        self._worker = ScriptRunnerWorker(module, argv)
        self._worker.output_line.connect(self.log_viewer.append_line)
        self._worker.error.connect(self.log_viewer.append_error)
        self._worker.finished_signal.connect(self._on_batch_step_finished)
        self._worker.start()

    def _on_batch_step_finished(self, exit_code: int) -> None:
        if exit_code == 0:
            self.log_viewer.append_line("[GUI] Step completed successfully")
        else:
            self.log_viewer.append_error(
                f"[GUI] Step finished with exit code {exit_code}"
            )
        self._worker = None
        self._run_next_batch()

    def _on_cancel(self) -> None:
        self._batch_queue.clear()
        if self._worker and self._worker.isRunning():
            self._worker.cancel()
            self.log_viewer.append_error("[GUI] Cancelled by user")
        self.run_controls.set_running(False)

    def _on_finished(self, exit_code: int) -> None:
        self.run_controls.set_running(False)
        pfx = "accuracy.sql_extract"
        if exit_code == 0:
            self.log_viewer.append_line("[GUI] Completed successfully")
            _update_last_run(self._last_run, pfx, True)
        else:
            self.log_viewer.append_error(
                f"[GUI] Finished with exit code {exit_code}"
            )
            _update_last_run(self._last_run, pfx, False)
        self._worker = None


# ---------------------------------------------------------------------------
# Accuracy Template Generator panel
# ---------------------------------------------------------------------------

class TemplateGeneratorPanel(QWidget):
    """Panel for the accuracy template generator script."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._worker: Optional[ScriptRunnerWorker] = None
        pfx = "accuracy.template_gen"

        inner = QWidget()
        layout = QVBoxLayout(inner)
        layout.addWidget(QLabel("<b>Accuracy Template Generator</b>"))
        layout.addWidget(_subtitle(
            "Generate accuracy testing template files from error and query CSVs"
        ))

        self._last_run = _last_run_label()
        _restore_last_run(self._last_run, pfx)
        layout.addWidget(self._last_run)

        self.config_loader = ConfigLoaderWidget()
        layout.addWidget(self.config_loader)

        # Input files group
        files_group = QGroupBox("Input Files")
        files_layout = QVBoxLayout(files_group)

        self.errors_csv = FilePickerWidget(
            "Validation errors CSV:",
            mode="file",
            tooltip="CSV containing validation errors to generate templates from.\nExample: buyer_errors_Q4_2025.csv",
            settings_key=f"{pfx}.errors_csv",
        )
        files_layout.addWidget(self.errors_csv)

        self.queries_csv = FilePickerWidget(
            "Accuracy query results CSV:",
            mode="file",
            tooltip="CSV containing accuracy query results.\nExample: buyer_queries_Q4_2025.csv",
            settings_key=f"{pfx}.queries_csv",
        )
        files_layout.addWidget(self.queries_csv)

        self.output_dir = FilePickerWidget(
            "Output directory:",
            mode="directory",
            tooltip="Directory where generated template files will be saved.",
            settings_key=f"{pfx}.output_dir",
        )
        files_layout.addWidget(self.output_dir)

        layout.addWidget(files_group)

        self.dry_run = FormFieldWidget(
            "Dry Run", field_type="checkbox",
            tooltip="Simulate the run without writing output files.",
            settings_key=f"{pfx}.dry_run",
        )
        layout.addWidget(self.dry_run)

        self.run_controls = RunControlsWidget()
        self.run_controls.run_clicked.connect(self._on_run)
        self.run_controls.dry_run_clicked.connect(self._on_dry_run)
        self.run_controls.cancel_clicked.connect(self._on_cancel)
        layout.addWidget(self.run_controls)

        self.log_viewer = LogViewerWidget()
        layout.addWidget(self.log_viewer, stretch=1)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(_scrollable(inner))

    def build_argv(self) -> List[str]:
        argv: List[str] = ["--gui-mode"]
        config_path = self.config_loader.get_last_path()
        if config_path:
            argv.extend(["--config", config_path])

        errors = self.errors_csv.get_path()
        if errors:
            argv.extend(["--errors", errors])
        queries = self.queries_csv.get_path()
        if queries:
            argv.extend(["--queries", queries])
        output = self.output_dir.get_path()
        if output:
            argv.extend(["--output", output])
        if self.dry_run.get_value():
            argv.append("--dry-run")
        return argv

    def _on_run(self) -> None:
        self._execute(dry_run=False)

    def _on_dry_run(self) -> None:
        self._execute(dry_run=True)

    def _execute(self, dry_run: bool = False) -> None:
        module = _import_script(
            "accuracy_testing.scripts.accuracy_template_generator"
        )
        if module is None:
            self.log_viewer.append_error(
                "Failed to import accuracy_template_generator"
            )
            return
        argv = self.build_argv()
        if dry_run and "--dry-run" not in argv:
            argv.append("--dry-run")
        self.log_viewer.clear()
        self.log_viewer.append_line(
            f"[GUI] Running: accuracy_template_generator {' '.join(argv)}"
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
        pfx = "accuracy.template_gen"
        if exit_code == 0:
            self.log_viewer.append_line("[GUI] Completed successfully")
            _update_last_run(self._last_run, pfx, True)
        else:
            self.log_viewer.append_error(
                f"[GUI] Finished with exit code {exit_code}"
            )
            _update_last_run(self._last_run, pfx, False)
        self._worker = None


# ---------------------------------------------------------------------------
# CSV Collation panel
# ---------------------------------------------------------------------------

class CollationPanel(QWidget):
    """Panel for the CSV collation script."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._worker: Optional[ScriptRunnerWorker] = None
        pfx = "accuracy.collation"

        inner = QWidget()
        layout = QVBoxLayout(inner)
        layout.addWidget(QLabel("<b>CSV Collation</b>"))
        layout.addWidget(_subtitle(
            "Collate per-incident CSV extract files into a single output"
        ))

        self._last_run = _last_run_label()
        _restore_last_run(self._last_run, pfx)
        layout.addWidget(self._last_run)

        self.config_loader = ConfigLoaderWidget()
        layout.addWidget(self.config_loader)

        # Input files group
        files_group = QGroupBox("Directories & Output")
        files_layout = QVBoxLayout(files_group)

        self.input_dir = FilePickerWidget(
            "Input directory:",
            mode="directory",
            tooltip="Directory containing individual incident CSV extracts.\nExample: data/extracts/",
            settings_key=f"{pfx}.input_dir",
        )
        files_layout.addWidget(self.input_dir)

        self.output_dir = FilePickerWidget(
            "Output directory:",
            mode="directory",
            tooltip="Directory for writing collated outputs.",
            settings_key=f"{pfx}.output_dir",
        )
        files_layout.addWidget(self.output_dir)

        self.output_file = FilePickerWidget(
            "Output file:",
            mode="save",
            tooltip="Single output CSV file path.\nExample: collated_Q4_2025.csv",
            settings_key=f"{pfx}.output_file",
        )
        files_layout.addWidget(self.output_file)

        layout.addWidget(files_group)

        # Incident selector (replaces free-text incidents field)
        self.incident_selector = IncidentSelectorWidget(
            ACCURACY_INCIDENTS,
            settings_key=f"{pfx}.selected_incidents",
        )
        layout.addWidget(self.incident_selector)

        self.incident = FormFieldWidget(
            "Single incident code:", field_type="text",
            tooltip="Run collation for a single incident only.\nExample: 7_5",
            placeholder="7_5",
            settings_key=f"{pfx}.incident",
        )
        layout.addWidget(self.incident)

        self.all_incidents = FormFieldWidget(
            "All Incidents", field_type="checkbox",
            tooltip="Collate all incidents regardless of selection.",
            settings_key=f"{pfx}.all_incidents",
        )
        layout.addWidget(self.all_incidents)

        # Period fields
        period_group = QGroupBox("Reporting Period")
        period_layout = QVBoxLayout(period_group)

        self.fiscal_year = FormFieldWidget(
            "Fiscal year:", field_type="text",
            tooltip="Fiscal year for filtering.\nExample: 2025",
            placeholder="2025",
            settings_key=f"{pfx}.fiscal_year",
        )
        period_layout.addWidget(self.fiscal_year)

        self.quarter = FormFieldWidget(
            "Quarter:", field_type="text",
            tooltip="Quarter for filtering.\nExample: Q4",
            placeholder="Q4",
            settings_key=f"{pfx}.quarter",
        )
        period_layout.addWidget(self.quarter)

        layout.addWidget(period_group)

        # Options
        options_group = QGroupBox("Options")
        options_layout = QVBoxLayout(options_group)

        self.log_level = FormFieldWidget(
            "Log Level:", field_type="dropdown",
            choices=LOG_LEVELS, default="INFO",
            tooltip="Logging verbosity level.",
            settings_key=f"{pfx}.log_level",
        )
        options_layout.addWidget(self.log_level)

        self.dry_run = FormFieldWidget(
            "Dry Run", field_type="checkbox",
            tooltip="Simulate the run without writing output files.",
            settings_key=f"{pfx}.dry_run",
        )
        options_layout.addWidget(self.dry_run)

        self.verbose = FormFieldWidget(
            "Verbose", field_type="checkbox",
            tooltip="Enable verbose output.",
            settings_key=f"{pfx}.verbose",
        )
        options_layout.addWidget(self.verbose)

        layout.addWidget(options_group)

        # Advanced (collapsible)
        self._advanced_btn = QPushButton("\u25b6 Advanced")
        self._advanced_btn.setFlat(True)
        self._advanced_btn.setStyleSheet("text-align: left; padding: 2px;")
        self._advanced_btn.clicked.connect(self._toggle_advanced)
        layout.addWidget(self._advanced_btn)

        self._advanced_widget = QWidget()
        adv_layout = QVBoxLayout(self._advanced_widget)
        adv_layout.setContentsMargins(10, 0, 0, 0)

        self.force = FormFieldWidget(
            "Force Overwrite", field_type="checkbox",
            tooltip="Overwrite output files without confirmation.",
            settings_key=f"{pfx}.force",
        )
        adv_layout.addWidget(self.force)

        self.delete_originals = FormFieldWidget(
            "Delete Originals", field_type="checkbox",
            tooltip="Delete source CSV files after successful collation.",
            settings_key=f"{pfx}.delete_originals",
        )
        adv_layout.addWidget(self.delete_originals)

        self._advanced_widget.setVisible(False)
        layout.addWidget(self._advanced_widget)

        self.run_controls = RunControlsWidget()
        self.run_controls.run_clicked.connect(self._on_run)
        self.run_controls.dry_run_clicked.connect(self._on_dry_run)
        self.run_controls.cancel_clicked.connect(self._on_cancel)
        layout.addWidget(self.run_controls)

        self.log_viewer = LogViewerWidget()
        layout.addWidget(self.log_viewer, stretch=1)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(_scrollable(inner))

    def _toggle_advanced(self) -> None:
        visible = not self._advanced_widget.isVisible()
        self._advanced_widget.setVisible(visible)
        self._advanced_btn.setText(
            "\u25bc Advanced" if visible else "\u25b6 Advanced"
        )

    def build_argv(self) -> List[str]:
        argv: List[str] = ["--gui-mode"]
        config_path = self.config_loader.get_last_path()
        if config_path:
            argv.extend(["--config", config_path])

        for field, flag in [
            (self.input_dir, "--input-dir"),
            (self.output_dir, "--output-dir"),
            (self.output_file, "--output"),
        ]:
            val = field.get_path()
            if val:
                argv.extend([flag, val])

        # Incident selection
        incident_val = self.incident.get_value()
        if incident_val:
            argv.extend(["--incident", incident_val])
        else:
            selected = self.incident_selector.get_selected()
            if selected:
                argv.extend(["--incidents", ",".join(selected)])

        for field, flag in [
            (self.fiscal_year, "--fiscal-year"),
            (self.quarter, "--quarter"),
        ]:
            val = field.get_value()
            if val:
                argv.extend([flag, val])

        log_level = self.log_level.get_value()
        if log_level:
            argv.extend(["--log-level", log_level])
        if self.all_incidents.get_value():
            argv.append("--all-incidents")
        if self.dry_run.get_value():
            argv.append("--dry-run")
        if self.force.get_value():
            argv.append("--force")
        if self.delete_originals.get_value():
            argv.append("--delete-originals")
        if self.verbose.get_value():
            argv.append("--verbose")
        return argv

    def _on_run(self) -> None:
        self._execute(dry_run=False)

    def _on_dry_run(self) -> None:
        self._execute(dry_run=True)

    def _execute(self, dry_run: bool = False) -> None:
        module = _import_script(
            "accuracy_testing.scripts.collate_csv_extracts"
        )
        if module is None:
            self.log_viewer.append_error(
                "Failed to import collate_csv_extracts"
            )
            return
        argv = self.build_argv()
        if dry_run and "--dry-run" not in argv:
            argv.append("--dry-run")
        self.log_viewer.clear()
        self.log_viewer.append_line(
            f"[GUI] Running: collate_csv_extracts {' '.join(argv)}"
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
        pfx = "accuracy.collation"
        if exit_code == 0:
            self.log_viewer.append_line("[GUI] Completed successfully")
            _update_last_run(self._last_run, pfx, True)
        else:
            self.log_viewer.append_error(
                f"[GUI] Finished with exit code {exit_code}"
            )
            _update_last_run(self._last_run, pfx, False)
        self._worker = None


# ---------------------------------------------------------------------------
# Data Push panel
# ---------------------------------------------------------------------------

class DataPushPanel(QWidget):
    """Panel for the data push script."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._worker: Optional[ScriptRunnerWorker] = None
        pfx = "accuracy.data_push"

        inner = QWidget()
        layout = QVBoxLayout(inner)
        layout.addWidget(QLabel("<b>Data Push</b>"))
        layout.addWidget(_subtitle(
            "Push validated accuracy data from source CSVs into target files"
        ))

        self._last_run = _last_run_label()
        _restore_last_run(self._last_run, pfx)
        layout.addWidget(self._last_run)

        self.config_loader = ConfigLoaderWidget()
        layout.addWidget(self.config_loader)

        # Single-file fields
        single_group = QGroupBox("Single File Mode")
        single_layout = QVBoxLayout(single_group)

        self.source_file = FilePickerWidget(
            "Source data CSV:",
            mode="file",
            tooltip="The validated source CSV to push from.\nExample: 7_5_buyer_results.csv",
            settings_key=f"{pfx}.source_file",
        )
        single_layout.addWidget(self.source_file)

        self.target_file = FilePickerWidget(
            "Target/accuracy CSV:",
            mode="file",
            tooltip="The target accuracy CSV to push data into.\nExample: accuracy_buyer_Q4.csv",
            settings_key=f"{pfx}.target_file",
        )
        single_layout.addWidget(self.target_file)

        self.output_file = FilePickerWidget(
            "Output file:",
            mode="save",
            tooltip="Where to write the merged output.\nExample: accuracy_buyer_Q4_updated.csv",
            settings_key=f"{pfx}.output_file",
        )
        single_layout.addWidget(self.output_file)

        self.incident = FormFieldWidget(
            "Single incident code:", field_type="text",
            tooltip="Incident code for single-file mode.\nExample: 7_5",
            placeholder="7_5",
            settings_key=f"{pfx}.incident",
        )
        single_layout.addWidget(self.incident)

        layout.addWidget(single_group)

        # Batch mode fields
        batch_group = QGroupBox("Batch Mode")
        batch_layout = QVBoxLayout(batch_group)

        self.batch_mode = FormFieldWidget(
            "Enable Batch Mode", field_type="checkbox",
            tooltip="Process multiple incidents by directory.",
            settings_key=f"{pfx}.batch_mode",
        )
        batch_layout.addWidget(self.batch_mode)

        self.source_dir = FilePickerWidget(
            "Source directory:",
            mode="directory",
            tooltip="Directory containing per-incident source CSV files.",
            settings_key=f"{pfx}.source_dir",
        )
        batch_layout.addWidget(self.source_dir)

        self.target_dir = FilePickerWidget(
            "Target directory:",
            mode="directory",
            tooltip="Directory containing per-incident target CSV files.",
            settings_key=f"{pfx}.target_dir",
        )
        batch_layout.addWidget(self.target_dir)

        self.incident_selector = IncidentSelectorWidget(
            ACCURACY_INCIDENTS,
            settings_key=f"{pfx}.selected_incidents",
        )
        batch_layout.addWidget(self.incident_selector)

        layout.addWidget(batch_group)

        # Period fields
        period_group = QGroupBox("Reporting Period")
        period_layout = QVBoxLayout(period_group)

        self.fiscal_year = FormFieldWidget(
            "Fiscal year:", field_type="text",
            tooltip="Fiscal year for naming.\nExample: 2025",
            placeholder="2025",
            settings_key=f"{pfx}.fiscal_year",
        )
        period_layout.addWidget(self.fiscal_year)

        self.quarter = FormFieldWidget(
            "Quarter:", field_type="text",
            tooltip="Quarter for naming.\nExample: Q4",
            placeholder="Q4",
            settings_key=f"{pfx}.quarter",
        )
        period_layout.addWidget(self.quarter)

        layout.addWidget(period_group)

        # Options
        options_group = QGroupBox("Options")
        options_layout = QVBoxLayout(options_group)

        self.log_level = FormFieldWidget(
            "Log Level:", field_type="dropdown",
            choices=LOG_LEVELS, default="INFO",
            tooltip="Logging verbosity level.",
            settings_key=f"{pfx}.log_level",
        )
        options_layout.addWidget(self.log_level)

        self.dry_run = FormFieldWidget(
            "Dry Run", field_type="checkbox",
            tooltip="Simulate the run without writing output files.",
            settings_key=f"{pfx}.dry_run",
        )
        options_layout.addWidget(self.dry_run)

        self.verbose = FormFieldWidget(
            "Verbose", field_type="checkbox",
            tooltip="Enable verbose output.",
            settings_key=f"{pfx}.verbose",
        )
        options_layout.addWidget(self.verbose)

        layout.addWidget(options_group)

        # Advanced (collapsible)
        self._advanced_btn = QPushButton("\u25b6 Advanced")
        self._advanced_btn.setFlat(True)
        self._advanced_btn.setStyleSheet("text-align: left; padding: 2px;")
        self._advanced_btn.clicked.connect(self._toggle_advanced)
        layout.addWidget(self._advanced_btn)

        self._advanced_widget = QWidget()
        adv_layout = QVBoxLayout(self._advanced_widget)
        adv_layout.setContentsMargins(10, 0, 0, 0)

        self.no_backup = FormFieldWidget(
            "No Backup", field_type="checkbox",
            tooltip="Skip creating a backup of the target file before overwriting.",
            settings_key=f"{pfx}.no_backup",
        )
        adv_layout.addWidget(self.no_backup)

        self._advanced_widget.setVisible(False)
        layout.addWidget(self._advanced_widget)

        self.run_controls = RunControlsWidget()
        self.run_controls.run_clicked.connect(self._on_run)
        self.run_controls.dry_run_clicked.connect(self._on_dry_run)
        self.run_controls.cancel_clicked.connect(self._on_cancel)
        layout.addWidget(self.run_controls)

        self.log_viewer = LogViewerWidget()
        layout.addWidget(self.log_viewer, stretch=1)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(_scrollable(inner))

    def _toggle_advanced(self) -> None:
        visible = not self._advanced_widget.isVisible()
        self._advanced_widget.setVisible(visible)
        self._advanced_btn.setText(
            "\u25bc Advanced" if visible else "\u25b6 Advanced"
        )

    def build_argv(self) -> List[str]:
        argv: List[str] = ["--gui-mode"]
        config_path = self.config_loader.get_last_path()
        if config_path:
            argv.extend(["--config", config_path])

        if self.batch_mode.get_value():
            argv.append("--batch")

        for picker, flag in [
            (self.source_file, "--source"),
            (self.target_file, "--target"),
            (self.output_file, "--output"),
            (self.source_dir, "--source-dir"),
            (self.target_dir, "--target-dir"),
        ]:
            val = picker.get_path()
            if val:
                argv.extend([flag, val])

        incident_val = self.incident.get_value()
        if incident_val:
            argv.extend(["--incident", incident_val])

        if self.batch_mode.get_value():
            selected = self.incident_selector.get_selected()
            if selected:
                argv.extend(["--incidents", ",".join(selected)])

        for field, flag in [
            (self.fiscal_year, "--fiscal-year"),
            (self.quarter, "--quarter"),
        ]:
            val = field.get_value()
            if val:
                argv.extend([flag, val])

        log_level = self.log_level.get_value()
        if log_level:
            argv.extend(["--log-level", log_level])
        if self.dry_run.get_value():
            argv.append("--dry-run")
        if self.no_backup.get_value():
            argv.append("--no-backup")
        if self.verbose.get_value():
            argv.append("--verbose")
        return argv

    def _on_run(self) -> None:
        self._execute(dry_run=False)

    def _on_dry_run(self) -> None:
        self._execute(dry_run=True)

    def _execute(self, dry_run: bool = False) -> None:
        module = _import_script("accuracy_testing.scripts.data_push")
        if module is None:
            self.log_viewer.append_error("Failed to import data_push")
            return
        argv = self.build_argv()
        if dry_run and "--dry-run" not in argv:
            argv.append("--dry-run")
        self.log_viewer.clear()
        self.log_viewer.append_line(
            f"[GUI] Running: data_push {' '.join(argv)}"
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
        pfx = "accuracy.data_push"
        if exit_code == 0:
            self.log_viewer.append_line("[GUI] Completed successfully")
            _update_last_run(self._last_run, pfx, True)
        else:
            self.log_viewer.append_error(
                f"[GUI] Finished with exit code {exit_code}"
            )
            _update_last_run(self._last_run, pfx, False)
        self._worker = None


# ---------------------------------------------------------------------------
# Main Accuracy Tab
# ---------------------------------------------------------------------------

_SECTION_BG = QColor("#e0e0e0")


class AccuracyTab(QWidget):
    """Accuracy Testing tab with sidebar navigation and stacked panels."""

    # (sidebar label, panel class, kwargs)
    PANELS = [
        ("Buyer ID", BaseValidationPanel,
         {"script_module_path": "accuracy_testing.scripts.buyer_id_validation",
          "title": "Buyer ID Validation",
          "subtitle": "Validates buyer identification data (incidents 7_5, 7_6)",
          "settings_prefix": "buyer_id"}),
        ("Seller ID", BaseValidationPanel,
         {"script_module_path": "accuracy_testing.scripts.seller_id_validation",
          "title": "Seller ID Validation",
          "subtitle": "Validates seller identification data (incidents 7_7, 7_8)",
          "settings_prefix": "seller_id"}),
        ("Inconsistent Buyer", BaseValidationPanel,
         {"script_module_path": "accuracy_testing.scripts.inconsistent_buyer_id_validation",
          "title": "Inconsistent Buyer ID Validation",
          "subtitle": "Detects inconsistent buyer IDs across transactions (incidents 7_37, 7_38)",
          "settings_prefix": "inconsistent_buyer"}),
        ("Inconsistent Seller", BaseValidationPanel,
         {"script_module_path": "accuracy_testing.scripts.inconsistent_seller_id_validation",
          "title": "Inconsistent Seller ID Validation",
          "subtitle": "Detects inconsistent seller IDs across transactions (incidents 7_39, 7_40)",
          "settings_prefix": "inconsistent_seller"}),
        ("FTBDM", DecisionMakerPanel,
         {"script_module_path": "accuracy_testing.scripts.validate_ftbdm",
          "title": "FTBDM Validation",
          "subtitle": "Field 27 Buyer Decision Maker validation",
          "settings_prefix": "ftbdm"}),
        ("FTSDM", DecisionMakerPanel,
         {"script_module_path": "accuracy_testing.scripts.validate_ftsdm",
          "title": "FTSDM Validation",
          "subtitle": "Field 28 Seller Decision Maker validation",
          "settings_prefix": "ftsdm"}),
        ("Pricing", BaseValidationPanel,
         {"script_module_path": "accuracy_testing.scripts.pricing_validation",
          "title": "Pricing Validation",
          "subtitle": "Validates transaction pricing fields",
          "settings_prefix": "pricing"}),
        ("Non-Zero Qty", BaseValidationPanel,
         {"script_module_path": "accuracy_testing.scripts.non_zero_net_quantity",
          "title": "Non-Zero Net Quantity Validation",
          "subtitle": "Checks that net quantity is non-zero where required",
          "settings_prefix": "non_zero_qty"}),
        ("Non-Zero Amt", BaseValidationPanel,
         {"script_module_path": "accuracy_testing.scripts.non_zero_net_amount",
          "title": "Non-Zero Net Amount Validation",
          "subtitle": "Checks that net amount is non-zero where required",
          "settings_prefix": "non_zero_amt"}),
        ("Run All", RunAllPanel, {}),
        (None, None, {}),  # Section separator
        ("SQL Extract", SQLExtractPanel, {}),
        ("Templates", TemplateGeneratorPanel, {}),
        ("CSV Collation", CollationPanel, {}),
        ("Data Push", DataPushPanel, {}),
    ]

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)

        layout = QHBoxLayout(self)

        # Sidebar
        self._sidebar = QListWidget()
        self._sidebar.setFixedWidth(180)
        self._sidebar.currentRowChanged.connect(self._on_sidebar_changed)
        layout.addWidget(self._sidebar)

        # Stacked panels
        self._stack = QStackedWidget()
        layout.addWidget(self._stack, stretch=1)

        # Build panels
        self._separator_rows: List[int] = []
        row = 0
        for label, panel_cls, kwargs in self.PANELS:
            if label is None:
                # Section header separator
                header_item = QListWidgetItem("  Utilities")
                header_item.setFlags(
                    header_item.flags()
                    & ~Qt.ItemFlag.ItemIsSelectable
                    & ~Qt.ItemFlag.ItemIsEnabled
                )
                header_item.setBackground(_SECTION_BG)
                header_font = QFont()
                header_font.setBold(True)
                header_item.setFont(header_font)
                self._sidebar.addItem(header_item)
                self._separator_rows.append(row)
                self._stack.addWidget(QWidget())
            else:
                self._sidebar.addItem(label)
                if panel_cls is not None:
                    panel = panel_cls(**kwargs)
                    self._stack.addWidget(panel)
                else:
                    self._stack.addWidget(QWidget())
            row += 1

        self._sidebar.setCurrentRow(0)

    def _on_sidebar_changed(self, index: int) -> None:
        """Switch the visible panel when sidebar selection changes."""
        if index in self._separator_rows:
            return
        self._stack.setCurrentIndex(index)

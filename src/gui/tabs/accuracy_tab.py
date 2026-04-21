#!/usr/bin/env python3
"""
Accuracy Testing Tab
====================

API-backed accuracy testing interface with:

- **Validation Scripts** panel — unified incident-driven UI with
  testing period selector, smart path config, hierarchical incident
  checklist, auto-discovery, per-incident file table, and run via
  the FastAPI backend.
- **Utilities** section with four panels (Template Generator,
  Extract Generator, CSV Collation, Data Push), each calling the
  API with an ``ApiWorker``.

Mirrors the web app's ``AccuracyTesting`` page within PySide6
constraints.

Version 2.0 Changes:
- Replaced direct script execution with API-backed ``ApiWorker``
- Replaced 9 individual validation panels + Run All with a single
  unified ``ValidationScriptsPanel``
- Added hierarchical incident selector with tree view
- Added ``IncidentFileTableWidget`` for per-incident path editing
- Added auto-discovery button that calls the API
"""

from typing import Any, Dict, List, Optional, Tuple
import os
import tempfile

import yaml
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from gui.api.client import ApiClient
from gui.constants import (
    CSV_FILTER,
    FISCAL_YEARS,
    INCIDENT_SCRIPT_MODULES,
    INCIDENT_SCRIPTS,
    LOG_LEVELS,
    QUARTERS,
)
from gui.utils.file_discovery_service import FileDiscoveryService, FileCandidate
from gui.utils.settings import settings
from gui.widgets import (
    FilePickerWidget,
    FormFieldWidget,
    IncidentSelectorWidget,
    LogViewerWidget,
    PreRunCheckWidget,
    RunControlsWidget,
    SmartPathConfigWidget,
    TestingPeriodWidget,
)
from gui.widgets.incident_file_table import IncidentFileTableWidget
from gui.widgets.pre_run_check import FileCheck
from gui.widgets.status_badge import StatusBadgeWidget
from gui.workers import ApiWorker, ScriptRunnerWorker


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


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


def _section_header(text: str) -> QLabel:
    """Create a bold section header label."""
    lbl = QLabel(text)
    font = lbl.font()
    font.setBold(True)
    font.setPointSize(font.pointSize() + 1)
    lbl.setFont(font)
    return lbl


def _current_fy() -> str:
    """Return the current fiscal year string, e.g. ``'FY26'``."""
    from datetime import datetime

    return f"FY{datetime.now().year % 100}"


# ---------------------------------------------------------------------------
# Testing Period Selector (reusable across panels)
# ---------------------------------------------------------------------------


class _TestingPeriodSelector(QWidget):
    """Fiscal year + quarter selector with QSettings persistence."""

    def __init__(
        self, settings_prefix: str = "accuracy", parent: Optional[QWidget] = None
    ) -> None:
        super().__init__(parent)
        self._prefix = settings_prefix

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        layout.addWidget(QLabel("Fiscal Year:"))
        self._fy = QComboBox()
        self._fy.addItems(FISCAL_YEARS)
        saved_fy = settings.load(f"{self._prefix}.fiscal_year", _current_fy())
        idx = self._fy.findText(str(saved_fy))
        if idx >= 0:
            self._fy.setCurrentIndex(idx)
        self._fy.currentTextChanged.connect(
            lambda t: settings.save(f"{self._prefix}.fiscal_year", t)
        )
        layout.addWidget(self._fy)

        layout.addWidget(QLabel("Quarter:"))
        self._q = QComboBox()
        self._q.addItems(QUARTERS)
        saved_q = settings.load(f"{self._prefix}.quarter", "Q1")
        idx = self._q.findText(str(saved_q))
        if idx >= 0:
            self._q.setCurrentIndex(idx)
        self._q.currentTextChanged.connect(
            lambda t: settings.save(f"{self._prefix}.quarter", t)
        )
        layout.addWidget(self._q)

        layout.addStretch()

    @property
    def fiscal_year(self) -> str:
        """Currently selected fiscal year."""
        return self._fy.currentText()

    @property
    def quarter(self) -> str:
        """Currently selected quarter."""
        return self._q.currentText()


# ---------------------------------------------------------------------------
# Smart Path Config (base dir → derived paths)
# ---------------------------------------------------------------------------


class _SmartPathConfig(QWidget):
    """Base directory selector that derives extract/template/output paths.

    Mirrors the web app's ``SmartPathConfig`` component.
    """

    def __init__(
        self, settings_prefix: str = "accuracy", parent: Optional[QWidget] = None
    ) -> None:
        super().__init__(parent)
        self._prefix = settings_prefix

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._base_dir = FilePickerWidget(
            "Base directory:",
            mode="directory",
            tooltip="Root directory containing extracts/, templates/, output/ sub-folders.",
            settings_key=f"{self._prefix}.base_dir",
        )
        layout.addWidget(self._base_dir)

        # Derived path labels
        self._extracts_lbl = QLabel("Extracts: —")
        self._templates_lbl = QLabel("Templates: —")
        self._output_lbl = QLabel("Output: —")
        for lbl in (self._extracts_lbl, self._templates_lbl, self._output_lbl):
            lbl.setStyleSheet("color: grey; font-size: 11px; margin-left: 8px;")
            layout.addWidget(lbl)

        self._base_dir.path_changed.connect(self._on_base_changed)

        # Initialise from saved value
        if self._base_dir.get_path():
            self._on_base_changed(self._base_dir.get_path())

    def _on_base_changed(self, base: str) -> None:
        """Derive sub-directory paths from the base."""
        if not base:
            self._extracts_lbl.setText("Extracts: —")
            self._templates_lbl.setText("Templates: —")
            self._output_lbl.setText("Output: —")
            return

        self._extracts_lbl.setText(f"Extracts: {base}/extracts")
        self._templates_lbl.setText(f"Templates: {base}/templates")
        self._output_lbl.setText(f"Output: {base}/output")

    @property
    def extracts_dir(self) -> str:
        """Path to the extracts sub-directory."""
        base = self._base_dir.get_path()
        return f"{base}/extracts" if base else ""

    @property
    def templates_dir(self) -> str:
        """Path to the templates sub-directory."""
        base = self._base_dir.get_path()
        return f"{base}/templates" if base else ""

    @property
    def output_dir(self) -> str:
        """Path to the output sub-directory."""
        base = self._base_dir.get_path()
        return f"{base}/output" if base else ""

    @property
    def kaizen_dir(self) -> str:
        """Path to the kaizen sub-directory (for template generator)."""
        base = self._base_dir.get_path()
        return f"{base}/kaizen" if base else ""

    @property
    def base_dir(self) -> str:
        """The raw base directory path."""
        return self._base_dir.get_path()


# ---------------------------------------------------------------------------
# Validation Scripts Panel (unified incident-driven)
# ---------------------------------------------------------------------------


class ValidationScriptsPanel(QWidget):
    """Unified validation scripts panel mirroring the web app.

    Features:
    - Testing period selector (FY + quarter)
    - Smart path configuration
    - Hierarchical incident checklist (grouped by script)
    - Auto-discovery button
    - Per-incident file table with Browse buttons
    - Stop on error checkbox
    - Advanced section (log level, dry run)
    - Run via ``ApiWorker`` → FastAPI → Celery
    """

    def __init__(
        self,
        api_client: ApiClient,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._api_client = api_client
        self._worker: Optional[ApiWorker] = None

        inner = QWidget()
        layout = QVBoxLayout(inner)

        # Title
        layout.addWidget(_section_header("Validation Scripts"))
        layout.addWidget(
            _subtitle(
                "Run selected incident validations against extract CSVs. "
                "Uses the FastAPI backend for execution."
            )
        )

        # --- Testing Period ---
        self._period = TestingPeriodWidget(
            settings_prefix="accuracy.validation", parent=self
        )
        layout.addWidget(self._period)

        # --- Smart Path Config ---
        self._paths = SmartPathConfigWidget(
            settings_prefix="accuracy.validation", parent=self
        )
        # Drive SmartPathConfigWidget from the period selector
        self._period.period_changed.connect(self._paths.set_period)
        self._paths.paths_resolved.connect(self._on_paths_resolved)
        # Set initial period so paths resolve on first paint
        self._paths.set_period(self._period.fiscal_year, self._period.quarter)
        layout.addWidget(self._paths)

        # --- Incident Checklist (hierarchical) ---
        self._incident_selector = IncidentSelectorWidget(
            incidents=[],
            settings_key="accuracy.validation.selected_incidents",
            hierarchical=True,
            parent=self,
        )
        self._incident_selector.set_scripts(INCIDENT_SCRIPTS)
        self._incident_selector.selection_changed.connect(self._on_selection_changed)
        layout.addWidget(self._incident_selector)

        # --- Discover Files button ---
        discover_row = QHBoxLayout()
        self._discover_btn = QPushButton("Discover Files")
        self._discover_btn.setToolTip(
            "Scan the extracts directory for matching incident files."
        )
        self._discover_btn.clicked.connect(self._on_discover)
        discover_row.addWidget(self._discover_btn)

        self._discover_status = QLabel("")
        self._discover_status.setStyleSheet("color: grey; font-size: 11px;")
        discover_row.addWidget(self._discover_status)
        discover_row.addStretch()
        layout.addLayout(discover_row)

        # --- Incident File Table ---
        self._file_table = IncidentFileTableWidget(
            show_template=True,
            collapsible=True,
            parent=self,
        )
        layout.addWidget(self._file_table)

        # Populate table from current selection
        self._on_selection_changed()

        # --- Stop on error ---
        self._stop_on_error = QCheckBox("Stop on first error")
        saved_stop = settings.load("accuracy.validation.stop_on_error", False)
        self._stop_on_error.setChecked(bool(saved_stop))
        self._stop_on_error.stateChanged.connect(
            lambda s: settings.save("accuracy.validation.stop_on_error", bool(s))
        )
        layout.addWidget(self._stop_on_error)

        # --- Advanced (collapsible) ---
        advanced_group = QGroupBox("Advanced")
        advanced_group.setCheckable(True)
        advanced_group.setChecked(False)
        adv_layout = QVBoxLayout(advanced_group)

        log_row = QHBoxLayout()
        log_row.addWidget(QLabel("Log Level:"))
        self._log_level = QComboBox()
        self._log_level.addItems(LOG_LEVELS)
        self._log_level.setCurrentText(
            str(settings.load("accuracy.validation.log_level", "INFO"))
        )
        self._log_level.currentTextChanged.connect(
            lambda t: settings.save("accuracy.validation.log_level", t)
        )
        log_row.addWidget(self._log_level)
        log_row.addStretch()
        adv_layout.addLayout(log_row)

        self._dry_run = QCheckBox("Dry Run")
        self._dry_run.setChecked(
            bool(settings.load("accuracy.validation.dry_run", False))
        )
        self._dry_run.stateChanged.connect(
            lambda s: settings.save("accuracy.validation.dry_run", bool(s))
        )
        adv_layout.addWidget(self._dry_run)

        layout.addWidget(advanced_group)

        # --- Pre-run checks ---
        self._pre_run_check = PreRunCheckWidget()
        self._pre_run_check.status_changed.connect(self._on_pre_run_status)
        layout.addWidget(self._pre_run_check)

        # --- Run Controls ---
        self._run_controls = RunControlsWidget()
        self._run_controls.run_clicked.connect(self._on_run)
        self._run_controls.cancel_clicked.connect(self._on_cancel)
        layout.addWidget(self._run_controls)

        # --- Last Run badge ---
        self._last_run = StatusBadgeWidget()
        layout.addWidget(self._last_run)

        # --- Log Viewer ---
        self._log_viewer = LogViewerWidget()
        layout.addWidget(self._log_viewer, stretch=1)

        layout.addStretch()

        self.setLayout(QVBoxLayout())
        self.layout().setContentsMargins(0, 0, 0, 0)
        self.layout().addWidget(_scrollable(inner))

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _on_selection_changed(self) -> None:
        """Rebuild the file table when incident selection changes."""
        selected = self._incident_selector.get_selected_incidents()
        incidents: List[Tuple[str, str]] = [
            (s["incidentCode"], s["scriptKey"]) for s in selected
        ]
        smart = self._paths.get_smart_paths()
        self._file_table.set_incidents(
            incidents,
            extracts_dir=smart.extracts if smart else "",
            templates_dir=smart.templates if smart else "",
            output_dir=smart.output if smart else "",
            fiscal_year=self._period.fiscal_year,
            quarter=self._period.quarter,
        )
        self._refresh_pre_run_checks()

    def _on_paths_resolved(self, smart_paths) -> None:
        """Refresh the file table and pre-run checks when paths change."""
        self._on_selection_changed()

    def _refresh_pre_run_checks(self) -> None:
        """Rebuild the pre-run check list from current incident configs."""
        if not hasattr(self, "_pre_run_check"):
            return  # Called during __init__ before widget is created
        configs = self._file_table.get_configs()
        checks: List[FileCheck] = []
        for c in configs:
            code = c.get("incidentCode", "")
            checks.append(
                FileCheck(
                    label=f"Extract ({code})",
                    path=c.get("inputFile", ""),
                    required=True,
                )
            )
            if c.get("templateFile"):
                checks.append(
                    FileCheck(
                        label=f"Template ({code})",
                        path=c.get("templateFile", ""),
                        required=False,
                    )
                )
        self._pre_run_check.set_checks(checks)

    def _on_pre_run_status(self, all_ok: bool) -> None:
        """Enable/disable the Run button based on pre-run check status."""
        self._run_controls._run_btn.setEnabled(all_ok)

    def _on_discover(self) -> None:
        """Scan the extracts directory locally to auto-populate file paths."""
        smart = self._paths.get_smart_paths()
        if not smart or not smart.extracts:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(
                self,
                "Validation",
                "Set a base directory and testing period first.",
            )
            return

        self._discover_btn.setEnabled(False)
        self._discover_status.setText("Scanning…")

        try:
            svc = FileDiscoveryService()
            # Collect all selected incident codes
            selected = self._incident_selector.get_selected_incidents()
            all_codes = [s["incidentCode"] for s in selected]
            if not all_codes:
                self._discover_status.setText("No incidents selected")
                return

            discovered = svc.discover_incident_files(
                smart, self._period.fiscal_year, self._period.quarter, all_codes
            )
            found_count = sum(1 for f in discovered.values() if f.input_found)
            self._discover_status.setText(
                f"Found {found_count}/{len(all_codes)} extract file(s)"
            )

            # Build discovery results in the format expected by populate_from_discovery
            script_key_map: Dict[str, str] = {}
            for s_def in INCIDENT_SCRIPTS:
                for inc in s_def["incidents"]:
                    script_key_map[inc["code"]] = s_def["scriptKey"]

            results = [
                {
                    "incidentCode": code,
                    "scriptKey": script_key_map.get(code, ""),
                    "filePath": inc_files.input_file,
                }
                for code, inc_files in discovered.items()
                if inc_files.input_found
            ]
            self._file_table.populate_from_discovery(results, script_key_map)
            self._refresh_pre_run_checks()
        except Exception as exc:
            self._discover_status.setText(f"Error: {exc}")
        finally:
            self._discover_btn.setEnabled(True)

    def _on_run(self) -> None:
        """Validate and run validation scripts locally via ScriptRunnerWorker."""
        selected = self._incident_selector.get_selected_incidents()
        if not selected:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "Validation", "Select at least one incident.")
            return

        configs = self._file_table.get_configs()
        missing = [c["incidentCode"] for c in configs if not c.get("inputFile")]
        if missing:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(
                self,
                "Validation",
                f"Input file missing for: {', '.join(missing)}",
            )
            return

        # Group incident configs by script key
        scripts_to_run: Dict[str, List[Dict[str, Any]]] = {}
        for c in configs:
            sk = c["scriptKey"]
            scripts_to_run.setdefault(sk, []).append(c)

        # Build run queue: list of (module_path, argv)
        self._run_queue: List[Tuple[str, List[str]]] = []
        self._temp_config_paths: List[str] = []
        for sk, inc_configs in scripts_to_run.items():
            module_path = INCIDENT_SCRIPT_MODULES.get(sk, "")
            if not module_path:
                self._log_viewer.append_error(
                    f"[GUI] No module path found for script key: {sk}"
                )
                continue
            yaml_path = self._write_batch_config(sk, inc_configs)
            argv = ["--config", yaml_path, "--gui-mode"]
            if self._dry_run.isChecked():
                argv.append("--dry-run")
            log_level = self._log_level.currentText()
            if log_level:
                argv.extend(["--log-level", log_level])
            self._run_queue.append((module_path, argv))

        if not self._run_queue:
            return

        self._log_viewer.clear()
        self._run_controls.set_running(True)
        self._run_errors: List[int] = []
        self._worker: Optional[ScriptRunnerWorker] = None
        self._start_next_run()

    def _write_batch_config(
        self, script_key: str, inc_configs: List[Dict[str, Any]]
    ) -> str:
        """Write a batch YAML config for one script and return the temp path."""
        smart = self._paths.get_smart_paths()
        incident_codes = [c["incidentCode"] for c in inc_configs]

        # Use smart paths as primary source; fall back to first config's dir
        extracts_dir = smart.extracts if smart else ""
        templates_dir = smart.templates if smart else ""
        output_dir = smart.output if smart else ""
        if not extracts_dir and inc_configs[0].get("inputFile"):
            extracts_dir = os.path.dirname(inc_configs[0]["inputFile"])
        if not templates_dir and inc_configs[0].get("templateFile"):
            templates_dir = os.path.dirname(inc_configs[0]["templateFile"])
        if not output_dir and inc_configs[0].get("outputFile"):
            output_dir = os.path.dirname(inc_configs[0]["outputFile"])

        config: Dict[str, Any] = {
            "mode": "batch",
            "testing_period": {
                "fiscal_year": self._period.fiscal_year,
                "quarter": self._period.quarter,
            },
            "batch": {
                "incidents": incident_codes,
                "paths": {
                    "extract_dir": extracts_dir,
                    "template_dir": templates_dir,
                    "output_dir": output_dir,
                },
                "filename_patterns": {
                    "extract": "{incident}_{fiscal_year}_{quarter}_extract.csv",
                    "template": "{fiscal_year} {quarter} {incident}.csv",
                    "output": "validated_{fiscal_year}_{quarter}_{incident}.csv",
                },
            },
            "processor": {
                "log_level": self._log_level.currentText() or "INFO",
            },
        }
        fd, path = tempfile.mkstemp(suffix=".yaml", prefix="gui_accuracy_")
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            yaml.safe_dump(config, fh, default_flow_style=False)
        self._temp_config_paths.append(path)
        return path

    def _start_next_run(self) -> None:
        """Pop and start the next script from the run queue."""
        if not self._run_queue:
            self._run_controls.set_running(False)
            if self._run_errors:
                self._last_run.set_status("failed")
                self._log_viewer.append_error(
                    "[GUI] One or more scripts finished with errors."
                )
            else:
                self._last_run.set_status("success")
                self._log_viewer.append_line(
                    "[GUI] All scripts completed successfully."
                )
            self._cleanup_temp_configs()
            self._worker = None
            return

        module_path, argv = self._run_queue.pop(0)
        import importlib
        module = importlib.import_module(module_path)
        self._log_viewer.append_line(f"\n[GUI] Running: {module_path}")
        self._worker = ScriptRunnerWorker(module, argv)
        self._worker.output_line.connect(self._log_viewer.append_line)
        self._worker.error.connect(self._log_viewer.append_error)
        self._worker.finished_signal.connect(self._on_script_finished)
        self._worker.start()

    def _on_script_finished(self, exit_code: int) -> None:
        """Called when one script in the queue finishes."""
        if exit_code != 0:
            self._run_errors.append(exit_code)
        if self._stop_on_error.isChecked() and self._run_errors:
            self._run_controls.set_running(False)
            self._last_run.set_status("failed")
            self._log_viewer.append_error("[GUI] Stopped on first error.")
            self._cleanup_temp_configs()
            self._worker = None
            return
        self._start_next_run()

    def _cleanup_temp_configs(self) -> None:
        """Delete all temp YAML config files written for this run."""
        for path in getattr(self, "_temp_config_paths", []):
            if os.path.isfile(path):
                try:
                    os.remove(path)
                except OSError:
                    pass
        self._temp_config_paths = []

    def _on_cancel(self) -> None:
        """Cancel a running job."""
        if self._worker and self._worker.isRunning():
            self._worker.terminate()
        self._run_queue = []
        self._run_controls.set_running(False)
        self._log_viewer.append_error("[GUI] Cancelled by user.")
        self._cleanup_temp_configs()
        self._worker = None

    def _on_finished(self, exit_code: int) -> None:
        """Handle job completion (legacy; kept for API-backed utility panels)."""
        self._run_controls.set_running(False)
        if exit_code == 0:
            self._last_run.set_status("success")
            self._log_viewer.append_line("\n[GUI] Validation completed successfully.")
        else:
            self._last_run.set_status("failed")
            self._log_viewer.append_error("\n[GUI] Validation failed.")
        self._worker = None


# ---------------------------------------------------------------------------
# Utility Panel Base
# ---------------------------------------------------------------------------


class _UtilityPanelBase(QWidget):
    """Base class for the four utility panels.

    Provides testing period selector, smart path config, log level,
    dry run, run controls, and log viewer.  Subclasses add their
    specific fields by implementing ``_build_fields()``.
    """

    _TITLE = "Utility"
    _SUBTITLE = ""
    _ENDPOINT = ""

    def __init__(
        self,
        api_client: ApiClient,
        settings_prefix: str = "",
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._api_client = api_client
        self._prefix = settings_prefix or self._TITLE.lower().replace(" ", "_")
        self._worker: Optional[ApiWorker] = None

        inner = QWidget()
        layout = QVBoxLayout(inner)

        layout.addWidget(_section_header(self._TITLE))
        if self._SUBTITLE:
            layout.addWidget(_subtitle(self._SUBTITLE))

        # Testing period
        self._period = _TestingPeriodSelector(
            settings_prefix=f"accuracy.{self._prefix}", parent=self
        )
        layout.addWidget(self._period)

        # Smart path config
        self._paths = _SmartPathConfig(
            settings_prefix=f"accuracy.{self._prefix}", parent=self
        )
        layout.addWidget(self._paths)

        # Subclass fields
        self._build_fields(layout)

        # Advanced
        advanced_group = QGroupBox("Advanced")
        advanced_group.setCheckable(True)
        advanced_group.setChecked(False)
        adv_layout = QVBoxLayout(advanced_group)

        log_row = QHBoxLayout()
        log_row.addWidget(QLabel("Log Level:"))
        self._log_level = QComboBox()
        self._log_level.addItems(LOG_LEVELS)
        self._log_level.setCurrentText(
            str(settings.load(f"accuracy.{self._prefix}.log_level", "INFO"))
        )
        self._log_level.currentTextChanged.connect(
            lambda t: settings.save(f"accuracy.{self._prefix}.log_level", t)
        )
        log_row.addWidget(self._log_level)
        log_row.addStretch()
        adv_layout.addLayout(log_row)

        self._dry_run = QCheckBox("Dry Run")
        self._dry_run.setChecked(
            bool(settings.load(f"accuracy.{self._prefix}.dry_run", False))
        )
        self._dry_run.stateChanged.connect(
            lambda s: settings.save(f"accuracy.{self._prefix}.dry_run", bool(s))
        )
        adv_layout.addWidget(self._dry_run)

        layout.addWidget(advanced_group)

        # Run controls
        self._run_controls = RunControlsWidget()
        self._run_controls.run_clicked.connect(self._on_run)
        self._run_controls.cancel_clicked.connect(self._on_cancel)
        layout.addWidget(self._run_controls)

        # Last run badge
        self._last_run = StatusBadgeWidget()
        layout.addWidget(self._last_run)

        # Log viewer
        self._log_viewer = LogViewerWidget()
        layout.addWidget(self._log_viewer, stretch=1)

        layout.addStretch()

        self.setLayout(QVBoxLayout())
        self.layout().setContentsMargins(0, 0, 0, 0)
        self.layout().addWidget(_scrollable(inner))

    def _build_fields(self, layout: QVBoxLayout) -> None:
        """Override in subclasses to add panel-specific fields."""

    def _build_payload(self) -> Optional[Dict[str, Any]]:
        """Override in subclasses to build the API payload.

        Returns:
            Payload dict, or ``None`` to abort the run.
        """
        return {}

    def _on_run(self) -> None:
        """Validate and submit the utility job to the API."""
        payload = self._build_payload()
        if payload is None:
            return

        self._log_viewer.clear()
        self._run_controls.set_running(True)

        self._worker = ApiWorker(
            client=self._api_client,
            endpoint=self._ENDPOINT,
            payload=payload,
        )
        self._worker.output_line.connect(self._log_viewer.append_line)
        self._worker.error.connect(self._log_viewer.append_error)
        self._worker.finished_signal.connect(self._on_finished)
        self._worker.start()

    def _on_cancel(self) -> None:
        """Cancel a running job."""
        if self._worker:
            self._worker.cancel()
        self._run_controls.set_running(False)
        self._log_viewer.append_error("[GUI] Cancelled.")

    def _on_finished(self, exit_code: int) -> None:
        """Handle job completion."""
        self._run_controls.set_running(False)
        if exit_code == 0:
            self._last_run.set_status("success")
            self._log_viewer.append_line(f"\n[GUI] {self._TITLE} completed successfully.")
        else:
            self._last_run.set_status("failed")
            self._log_viewer.append_error(f"\n[GUI] {self._TITLE} failed.")
        self._worker = None


# ---------------------------------------------------------------------------
# Template Generator Panel
# ---------------------------------------------------------------------------


class TemplateGeneratorPanel(_UtilityPanelBase):
    """Generate accuracy testing template files from Kaizen data."""

    _TITLE = "Template Generator"
    _SUBTITLE = (
        "Generate template CSVs from consolidated Kaizen error/query data."
    )
    _ENDPOINT = "/api/accuracy/run"

    def _build_fields(self, layout: QVBoxLayout) -> None:
        """Add incident selector and kaizen file fields."""
        # Incident selector (flat mode for utilities)
        self._incident_selector = IncidentSelectorWidget(
            incidents=[
                (s["scriptKey"], s["displayLabel"])
                for s in INCIDENT_SCRIPTS
            ],
            settings_key=f"accuracy.{self._prefix}.selected",
        )
        layout.addWidget(self._incident_selector)

        # Kaizen error/query file pickers (auto-populated from base dir)
        kaizen_group = QGroupBox("Kaizen Files")
        kaizen_layout = QVBoxLayout(kaizen_group)

        self._errors_csv = FilePickerWidget(
            "Consolidated Errors CSV:",
            mode="file",
            file_filter=CSV_FILTER,
            tooltip="Consolidated Kaizen errors data CSV.",
            settings_key=f"accuracy.{self._prefix}.errors_csv",
        )
        kaizen_layout.addWidget(self._errors_csv)

        self._queries_csv = FilePickerWidget(
            "Consolidated Queries CSV:",
            mode="file",
            file_filter=CSV_FILTER,
            tooltip="Consolidated Kaizen queries data CSV.",
            settings_key=f"accuracy.{self._prefix}.queries_csv",
        )
        kaizen_layout.addWidget(self._queries_csv)

        layout.addWidget(kaizen_group)

    def _build_payload(self) -> Optional[Dict[str, Any]]:
        """Build the template generator API payload."""
        return {
            "scriptName": "accuracy_template_generator",
            "testingPeriod": {
                "fiscalYear": self._period.fiscal_year,
                "quarter": self._period.quarter,
            },
            "mode": "batch",
            "batchConfig": {
                "inputDirectory": self._paths.kaizen_dir,
                "outputDirectory": self._paths.templates_dir,
                "templateDirectory": "",
                "logOutput": "logs",
            },
            "logLevel": self._log_level.currentText(),
            "dryRun": self._dry_run.isChecked(),
        }


# ---------------------------------------------------------------------------
# Extract Generator Panel (SQL Extract)
# ---------------------------------------------------------------------------


class ExtractGeneratorPanel(_UtilityPanelBase):
    """Generate SQL extract scripts and optionally execute DTF."""

    _TITLE = "Extract Generator"
    _SUBTITLE = (
        "Generate SQL extract batches from transaction reference CSVs."
    )
    _ENDPOINT = "/api/accuracy/run"

    def _build_fields(self, layout: QVBoxLayout) -> None:
        """Add incident selector and file table for extract inputs."""
        self._incident_selector = IncidentSelectorWidget(
            incidents=[
                (s["scriptKey"], s["displayLabel"])
                for s in INCIDENT_SCRIPTS
            ],
            settings_key=f"accuracy.{self._prefix}.selected",
        )
        self._incident_selector.selection_changed.connect(self._refresh_table)
        layout.addWidget(self._incident_selector)

        # File table (input only — no template column)
        self._file_table = IncidentFileTableWidget(
            show_template=False,
            collapsible=True,
            parent=self,
        )
        layout.addWidget(self._file_table)

        self._batch_size = FormFieldWidget(
            "Batch size:", field_type="spinbox", default=900,
            tooltip="Transaction references per SQL batch (default 900).",
            settings_key=f"accuracy.{self._prefix}.batch_size",
        )
        layout.addWidget(self._batch_size)

        self._refresh_table()

    def _refresh_table(self) -> None:
        """Rebuild the file table from selected incidents."""
        selected = self._incident_selector.get_selected()
        incidents: List[Tuple[str, str]] = []
        for s in INCIDENT_SCRIPTS:
            if s["scriptKey"] in selected:
                for inc in s["incidents"]:
                    incidents.append((inc["code"], s["scriptKey"]))
        self._file_table.set_incidents(
            incidents,
            extracts_dir=self._paths.extracts_dir,
            output_dir=self._paths.output_dir,
            fiscal_year=self._period.fiscal_year,
            quarter=self._period.quarter,
        )

    def _build_payload(self) -> Optional[Dict[str, Any]]:
        """Build the SQL extract generator API payload."""
        return {
            "scriptName": "sql_extract_generator",
            "testingPeriod": {
                "fiscalYear": self._period.fiscal_year,
                "quarter": self._period.quarter,
            },
            "mode": "batch",
            "batchConfig": {
                "inputDirectory": self._paths.extracts_dir,
                "outputDirectory": self._paths.output_dir,
                "templateDirectory": "",
                "logOutput": "logs",
            },
            "logLevel": self._log_level.currentText(),
            "dryRun": self._dry_run.isChecked(),
        }


# ---------------------------------------------------------------------------
# CSV Collation Panel
# ---------------------------------------------------------------------------


class CollatePanel(_UtilityPanelBase):
    """Collate per-incident extract CSVs into combined files."""

    _TITLE = "CSV Collation"
    _SUBTITLE = (
        "Collate individual extract CSVs into combined per-incident files."
    )
    _ENDPOINT = "/api/accuracy/run"

    def _build_fields(self, layout: QVBoxLayout) -> None:
        """Add incident selector."""
        self._incident_selector = IncidentSelectorWidget(
            incidents=[
                (s["scriptKey"], s["displayLabel"])
                for s in INCIDENT_SCRIPTS
            ],
            settings_key=f"accuracy.{self._prefix}.selected",
        )
        layout.addWidget(self._incident_selector)

    def _build_payload(self) -> Optional[Dict[str, Any]]:
        """Build the collation API payload."""
        return {
            "scriptName": "collate_csv_extracts",
            "testingPeriod": {
                "fiscalYear": self._period.fiscal_year,
                "quarter": self._period.quarter,
            },
            "mode": "batch",
            "batchConfig": {
                "inputDirectory": self._paths.extracts_dir,
                "outputDirectory": self._paths.extracts_dir,
                "templateDirectory": "",
                "logOutput": "logs",
            },
            "logLevel": self._log_level.currentText(),
            "dryRun": self._dry_run.isChecked(),
        }


# ---------------------------------------------------------------------------
# Data Push Panel
# ---------------------------------------------------------------------------


class DataPushPanel(_UtilityPanelBase):
    """Push validated data back into template CSVs."""

    _TITLE = "Data Push"
    _SUBTITLE = (
        "Write validated correction data back into template CSV files."
    )
    _ENDPOINT = "/api/accuracy/run"

    def _build_fields(self, layout: QVBoxLayout) -> None:
        """Add incident selector and file table for push paths."""
        self._incident_selector = IncidentSelectorWidget(
            incidents=[
                (s["scriptKey"], s["displayLabel"])
                for s in INCIDENT_SCRIPTS
            ],
            settings_key=f"accuracy.{self._prefix}.selected",
        )
        self._incident_selector.selection_changed.connect(self._refresh_table)
        layout.addWidget(self._incident_selector)

        self._file_table = IncidentFileTableWidget(
            show_template=True,
            collapsible=True,
            parent=self,
        )
        layout.addWidget(self._file_table)

        self._refresh_table()

    def _refresh_table(self) -> None:
        """Rebuild the file table from selected incidents."""
        selected = self._incident_selector.get_selected()
        incidents: List[Tuple[str, str]] = []
        for s in INCIDENT_SCRIPTS:
            if s["scriptKey"] in selected:
                for inc in s["incidents"]:
                    incidents.append((inc["code"], s["scriptKey"]))
        self._file_table.set_incidents(
            incidents,
            extracts_dir=self._paths.output_dir,
            templates_dir=self._paths.templates_dir,
            output_dir=self._paths.output_dir,
            fiscal_year=self._period.fiscal_year,
            quarter=self._period.quarter,
        )

    def _build_payload(self) -> Optional[Dict[str, Any]]:
        """Build the data push API payload."""
        configs = self._file_table.get_configs()
        return {
            "scriptName": "data_push",
            "testingPeriod": {
                "fiscalYear": self._period.fiscal_year,
                "quarter": self._period.quarter,
            },
            "mode": "batch",
            "batchConfig": {
                "inputDirectory": self._paths.output_dir,
                "outputDirectory": self._paths.output_dir,
                "templateDirectory": self._paths.templates_dir,
                "logOutput": "logs",
            },
            "logLevel": self._log_level.currentText(),
            "dryRun": self._dry_run.isChecked(),
        }


# ---------------------------------------------------------------------------
# Main Accuracy Tab
# ---------------------------------------------------------------------------

_SECTION_BG = QColor("#e0e0e0")


class AccuracyTab(QWidget):
    """Accuracy Testing tab with sidebar navigation and stacked panels.

    Layout:
    - Validation Scripts  (unified incident-driven panel)
    - --- Utilities ---
    - Template Generator
    - Extract Generator
    - CSV Collation
    - Data Push
    """

    def __init__(
        self,
        api_client: Optional[ApiClient] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._api_client = api_client or ApiClient()

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

        # -- Validation Scripts --
        self._sidebar.addItem("Validation Scripts")
        self._stack.addWidget(
            ValidationScriptsPanel(api_client=self._api_client)
        )
        row += 1

        # -- Section separator --
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
        self._stack.addWidget(QWidget())  # placeholder
        self._separator_rows.append(row)
        row += 1

        # -- Utility panels --
        utilities: List[tuple] = [
            ("Templates", TemplateGeneratorPanel, "template_gen"),
            ("Extracts", ExtractGeneratorPanel, "extract_gen"),
            ("CSV Collation", CollatePanel, "collate"),
            ("Data Push", DataPushPanel, "data_push"),
        ]
        for label, panel_cls, prefix in utilities:
            self._sidebar.addItem(label)
            self._stack.addWidget(
                panel_cls(
                    api_client=self._api_client,
                    settings_prefix=prefix,
                )
            )
            row += 1

        self._sidebar.setCurrentRow(0)

    def _on_sidebar_changed(self, index: int) -> None:
        """Switch the visible panel when sidebar selection changes."""
        if index in self._separator_rows:
            return
        self._stack.setCurrentIndex(index)

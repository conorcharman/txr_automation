#!/usr/bin/env python3
"""
Replay Processing Tab
=====================

Four replay processing script panels:
- Phase II
- Phase III - Feedback
- Phase III - Final Lookup
- Merge Inconsistent Summaries

Uses a sidebar list + stacked widget layout with per-panel log viewers.
Panels persist field values across sessions via QSettings caching.
"""

import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml
from PySide6.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QScrollArea,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from gui.constants import FISCAL_YEARS, LOG_LEVELS, QUARTERS
from gui.utils.settings import settings
from gui.widgets import (
    ConfigLoaderWidget,
    FilePickerWidget,
    FormFieldWidget,
    LogViewerWidget,
    PreRunCheckWidget,
    RunControlsWidget,
    TestingPeriodWidget,
)
from gui.widgets.pre_run_check import FileCheck
from gui.workers import ScriptRunnerWorker


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


def _scrollable(inner: QWidget) -> QScrollArea:
    """Wrap *inner* in a QScrollArea that resizes with its contents."""
    scroll = QScrollArea()
    scroll.setWidget(inner)
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(scroll.Shape.NoFrame)
    return scroll


# ---------------------------------------------------------------------------
# Default incident column mappings (standardised across all incident templates)
# ---------------------------------------------------------------------------

_PHASE2_INCIDENT_COLUMNS: Dict[str, str] = {
    "transaction_ref": "Transaction Reference",
    "error_flag": "Error",
    "correction": "Correction",
    "correction_field": "Correction Field",
    "agree_with_correction": "Agree With Correction",
    "suggested_correction": "Suggested Correction",
    "suggested_correction_field": "Suggested Correction Field",
}

_PHASE3_INCIDENT_COLUMNS: Dict[str, str] = {
    **_PHASE2_INCIDENT_COLUMNS,
    "buyer_id": "Buyer identification code",
    "buyer_first_name": "Buyer - First name(s)",
    "buyer_last_name": "Buyer - Surname(s)",
    "buyer_dob": "Buyer - Date of birth",
    "seller_id": "Seller identification code",
    "seller_first_name": "Seller - First name(s)",
    "seller_last_name": "Seller - Surname(s)",
    "seller_dob": "Seller - Date of birth",
    "buyer_dm_id": "Buyer decision maker code",
    "buyer_dm_first_name": "Buy decision maker - First name(s)",
    "buyer_dm_last_name": "Buy decision maker - Surname(s)",
    "buyer_dm_dob": "Buy decision maker - Date of birth",
    "seller_dm_id": "Sell decision maker code",
    "seller_dm_first_name": "Sell decision maker - First name(s)",
    "seller_dm_last_name": "Sell decision maker - Surname(s)",
    "seller_dm_dob": "Sell decision maker - Date of birth",
}


# ---------------------------------------------------------------------------
# Base replay panel (Phase 2 / Phase 3 style)
# ---------------------------------------------------------------------------

class BaseReplayPanel(QWidget):
    """Base panel for replay processor scripts.

    Provides testing period, path fields, options, and optional
    YAML config loading.  Direct fields take priority over loaded YAML;
    a temp config is generated at run time and passed to the script.
    """

    def __init__(
        self,
        script_module_path: str,
        title: str,
        subtitle: str = "",
        extra_paths: Optional[List[Dict[str, str]]] = None,
        extra_file_patterns: Optional[List[Dict[str, Any]]] = None,
        default_incident_columns: Optional[Dict[str, str]] = None,
        settings_prefix: str = "",
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._script_module_path = script_module_path
        self._worker: Optional[ScriptRunnerWorker] = None
        self._temp_config_path: Optional[str] = None
        self._loaded_config: Optional[Dict[str, Any]] = None
        self._file_pattern_fields: Dict[str, FormFieldWidget] = {}
        self._list_fields: set = set()
        self._default_incident_columns = default_incident_columns
        pfx = f"replay.{settings_prefix}" if settings_prefix else "replay"
        self._pfx = pfx

        inner = QWidget()
        layout = QVBoxLayout(inner)

        # --- Header ---
        layout.addWidget(QLabel(f"<b>{title}</b>"))
        if subtitle:
            layout.addWidget(_subtitle(subtitle))

        self._last_run = _last_run_label()
        _restore_last_run(self._last_run, pfx)
        layout.addWidget(self._last_run)

        # --- Configuration File (secondary) ---
        config_group = QGroupBox("Configuration File")
        config_layout = QVBoxLayout(config_group)
        self.config_loader = ConfigLoaderWidget()
        self.config_loader.config_loaded.connect(self.populate_from_config)
        config_layout.addWidget(self.config_loader)
        layout.addWidget(config_group)

        # --- Testing Period ---
        period_group = QGroupBox("Testing Period")
        period_layout = QVBoxLayout(period_group)
        self._period = TestingPeriodWidget(settings_prefix=pfx, parent=self)
        self._period.period_changed.connect(lambda _fy, _q: self._refresh_path_hints())
        period_layout.addWidget(self._period)
        layout.addWidget(period_group)

        # Keep legacy aliases so populate_from_config and build_argv work
        # unchanged; these are thin shims over _period.
        class _FYAlias:
            def __init__(self_, p): self_._p = p
            def get_value(self_): return self_._p.fiscal_year
            def set_value(self_, v): self_._p.set_period(v, self_._p.quarter)
        class _QAlias:
            def __init__(self_, p): self_._p = p
            def get_value(self_): return self_._p.quarter
            def set_value(self_, v): self_._p.set_period(self_._p.fiscal_year, v)
        self.fiscal_year = _FYAlias(self._period)
        self.quarter = _QAlias(self._period)

        # --- Paths ---
        paths_group = QGroupBox("Paths")
        paths_layout = QVBoxLayout(paths_group)

        self._path_pickers: Dict[str, FilePickerWidget] = {}
        if extra_paths:
            for path_def in extra_paths:
                picker = FilePickerWidget(
                    path_def["label"], mode="directory",
                    tooltip=path_def.get("tooltip", ""),
                    settings_key=f"{pfx}.{path_def['key']}",
                )
                paths_layout.addWidget(picker)
                self._path_pickers[path_def["key"]] = picker

        layout.addWidget(paths_group)

        # --- File Patterns ---
        if extra_file_patterns:
            patterns_group = QGroupBox("File Patterns")
            patterns_layout = QVBoxLayout(patterns_group)
            for pat_def in extra_file_patterns:
                key = pat_def["key"]
                field = FormFieldWidget(
                    pat_def["label"], field_type="text",
                    default=pat_def.get("default", ""),
                    tooltip=pat_def.get("tooltip", ""),
                    placeholder=pat_def.get("placeholder", ""),
                    settings_key=f"{pfx}.files.{key}",
                )
                patterns_layout.addWidget(field)
                self._file_pattern_fields[key] = field
                if pat_def.get("is_list", False):
                    self._list_fields.add(key)
            layout.addWidget(patterns_group)

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
        layout.addWidget(options_group)

        # --- Run controls + Log viewer ---
        self.run_controls = RunControlsWidget()
        self.run_controls.run_clicked.connect(self._on_run)
        self.run_controls.cancel_clicked.connect(self._on_cancel)
        # Hide dry-run (replay scripts don't support it)
        self.run_controls._dry_run_btn.setVisible(False)

        # Pre-run checks (input directory presence)
        self._pre_run_check = PreRunCheckWidget()
        self._pre_run_check.status_changed.connect(
            lambda ok: self.run_controls._run_btn.setEnabled(ok)
        )
        layout.addWidget(self._pre_run_check)
        layout.addWidget(self.run_controls)

        self.log_viewer = LogViewerWidget()
        layout.addWidget(self.log_viewer, stretch=1)

        # Wrap in scroll area
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(_scrollable(inner))

        # Refresh hints with initial values
        self._refresh_path_hints()

    # -- Path hint refresh ------------------------------------------------

    def _refresh_path_hints(self) -> None:
        """Update path picker tooltips with FY/Q context hints."""
        fy = self._period.fiscal_year or "FY__"
        qtr = self._period.quarter or "Q_"
        hint = f"\u2026/{fy}/{qtr}"
        for key, picker in self._path_pickers.items():
            base = picker.get_path()
            if base:
                continue  # don't overwrite a user-entered path tooltip
            picker.setToolTip(f"Expected path pattern: {hint}/{key}")
        self._refresh_pre_run_checks()

    def _refresh_pre_run_checks(self) -> None:
        """Update PreRunCheckWidget with first configured input directory."""
        checks: List[FileCheck] = []
        for key, picker in self._path_pickers.items():
            path = picker.get_path()
            if not path:
                continue
            import os
            # Check if a directory is non-empty (has CSV files)
            checks.append(
                FileCheck(
                    label=key.replace("_", " ").title(),
                    path=path,
                    required=(key in ("replay_input", "input_dir", "input")),
                )
            )
            break  # Only check the first (primary) path for now
        self._pre_run_check.set_checks(checks)

    # -- Config building --------------------------------------------------

    def _build_config_dict(self) -> Dict[str, Any]:
        """Generate a YAML-compatible config dict from direct fields.

        If the user loaded a YAML via the config loader, that YAML is
        used as a base and direct-field values are overlaid on top.
        """
        config: Dict[str, Any] = dict(self._loaded_config) if self._loaded_config else {}

        # Testing period metadata
        fy = self.fiscal_year.get_value()
        qtr = self.quarter.get_value()
        if fy or qtr:
            tp = config.setdefault("testing_period", {})
            if fy:
                tp["fiscal_year"] = fy
            if qtr:
                tp["quarter"] = qtr

        # Paths — overlay direct-field values on existing config paths
        paths = config.setdefault("paths", {})
        for key, picker in self._path_pickers.items():
            val = picker.get_path()
            if val:
                paths[key] = val

        # Processor options
        proc = config.setdefault("processor", {})
        log_level = self.log_level.get_value()
        if log_level:
            proc["log_level"] = log_level

        # File patterns — overlay direct-field values on existing config
        if self._file_pattern_fields:
            files = config.setdefault("files", {})
            for key, field in self._file_pattern_fields.items():
                val = field.get_value()
                if val:
                    if key in self._list_fields:
                        files[key] = [p.strip() for p in val.split(",") if p.strip()]
                    else:
                        files[key] = val

        # Incident columns — inject defaults if not already in config
        if self._default_incident_columns and not config.get("incident_columns"):
            config["incident_columns"] = dict(self._default_incident_columns)

        return config

    def _write_temp_config(self) -> str:
        """Write the merged config dict to a temp YAML file.

        Returns the path to the temp file.  The caller is responsible
        for cleanup (handled in _on_finished).
        """
        config = self._build_config_dict()
        fd, path = tempfile.mkstemp(suffix=".yaml", prefix="gui_replay_")
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            yaml.safe_dump(config, fh, default_flow_style=False)
        self._temp_config_path = path
        return path

    def _cleanup_temp_config(self) -> None:
        """Remove the temp config file if it exists."""
        if self._temp_config_path and os.path.isfile(self._temp_config_path):
            try:
                os.remove(self._temp_config_path)
            except OSError:
                pass
            self._temp_config_path = None

    # -- Argv building ----------------------------------------------------

    def build_argv(self) -> List[str]:
        """Build argv for the replay processor.

        Generates a temp config from direct fields (overlaid on any
        loaded YAML) and passes --config <tmp> --gui-mode.
        """
        argv: List[str] = ["--gui-mode"]

        # Generate temp config from direct fields (overlaid on loaded YAML)
        config_path = self._write_temp_config()
        argv.extend(["--config", config_path])

        log_level = self.log_level.get_value()
        if log_level:
            argv.extend(["--log-level", log_level])

        return argv

    # -- Config population ------------------------------------------------

    def populate_from_config(self, config: Dict[str, Any]) -> None:
        """Fill direct fields from loaded YAML config."""
        self._loaded_config = config

        # Testing period
        tp = config.get("testing_period", {})
        if tp.get("fiscal_year") and hasattr(self, "fiscal_year"):
            self.fiscal_year.set_value(tp["fiscal_year"])
        if tp.get("quarter") and hasattr(self, "quarter"):
            self.quarter.set_value(tp["quarter"])

        # Paths
        paths = config.get("paths", {})
        for key, picker in self._path_pickers.items():
            val = paths.get(key, "")
            if val:
                picker.set_path(str(val))

        # Processor
        proc = config.get("processor", {})
        if proc.get("log_level"):
            self.log_level.set_value(proc["log_level"])

        # File patterns
        files = config.get("files", {})
        for key, field in self._file_pattern_fields.items():
            val = files.get(key)
            if val is not None:
                if isinstance(val, list):
                    field.set_value(", ".join(val))
                else:
                    field.set_value(str(val))

    # -- Run / Cancel / Finished ------------------------------------------

    def _on_run(self) -> None:
        import importlib
        module = importlib.import_module(self._script_module_path)
        argv = self.build_argv()  # writes temp config, returns --config <path> --gui-mode
        self.log_viewer.clear()
        self.log_viewer.append_line(f"[GUI] Running: {self._script_module_path}")
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
        success = exit_code == 0
        if success:
            self.log_viewer.append_line("[GUI] Completed successfully")
        else:
            self.log_viewer.append_error(f"[GUI] Finished with exit code {exit_code}")
        _update_last_run(self._last_run, self._pfx, success)
        self._cleanup_temp_config()
        self._worker = None


# ---------------------------------------------------------------------------
# Merge Inconsistent Summaries panel
# ---------------------------------------------------------------------------

class MergeInconsistentPanel(QWidget):
    """Panel for the merge-inconsistent-summaries script."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._worker: Optional[ScriptRunnerWorker] = None
        self._loaded_config: Optional[Dict[str, Any]] = None
        pfx = "replay.merge_inconsistent"
        self._pfx = pfx

        inner = QWidget()
        layout = QVBoxLayout(inner)

        # --- Header ---
        layout.addWidget(QLabel("<b>Merge Inconsistent Summaries</b>"))
        layout.addWidget(_subtitle(
            "Merge Phase III inconsistent ID and name summary files"
        ))

        self._last_run = _last_run_label()
        _restore_last_run(self._last_run, pfx)
        layout.addWidget(self._last_run)

        # --- Configuration File (secondary) ---
        config_group = QGroupBox("Configuration File")
        config_layout = QVBoxLayout(config_group)
        self.config_loader = ConfigLoaderWidget()
        self.config_loader.config_loaded.connect(self.populate_from_config)
        config_layout.addWidget(self.config_loader)
        layout.addWidget(config_group)

        # --- Testing Period ---
        period_group = QGroupBox("Testing Period")
        period_layout = QVBoxLayout(period_group)
        self._period = TestingPeriodWidget(settings_prefix=pfx, parent=self)
        period_layout.addWidget(self._period)
        layout.addWidget(period_group)

        # Compatibility aliases (populate_from_config uses .get_value()/.set_value())
        class _FYAlias:
            def __init__(self_, p): self_._p = p
            def get_value(self_): return self_._p.fiscal_year
            def set_value(self_, v): self_._p.set_period(v, self_._p.quarter)
        class _QAlias:
            def __init__(self_, p): self_._p = p
            def get_value(self_): return self_._p.quarter
            def set_value(self_, v): self_._p.set_period(self_._p.fiscal_year, v)
        self.fiscal_year = _FYAlias(self._period)
        self.quarter = _QAlias(self._period)

        # --- Paths ---
        paths_group = QGroupBox("Paths")
        paths_layout = QVBoxLayout(paths_group)

        self.input_dir = FilePickerWidget(
            "Input Directory:", mode="directory",
            tooltip=(
                "Directory containing Phase III inconsistent ID\n"
                "and name summary CSV files."
            ),
            settings_key=f"{pfx}.input_dir",
        )
        paths_layout.addWidget(self.input_dir)
        layout.addWidget(paths_group)

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

        # --- Run controls + Log viewer ---
        self._pre_run_check = PreRunCheckWidget()
        self._pre_run_check.status_changed.connect(
            lambda ok: self.run_controls._run_btn.setEnabled(ok)
        )
        self.run_controls = RunControlsWidget()
        self.run_controls.run_clicked.connect(self._on_run)
        self.run_controls.dry_run_clicked.connect(self._on_dry_run)
        self.run_controls.cancel_clicked.connect(self._on_cancel)
        # Wire input_dir change → refresh pre-run check
        self.input_dir.path_changed.connect(self._refresh_pre_run_check)
        layout.addWidget(self._pre_run_check)
        layout.addWidget(self.run_controls)

        self.log_viewer = LogViewerWidget()
        layout.addWidget(self.log_viewer, stretch=1)

        # Wrap in scroll area
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(_scrollable(inner))

    def _refresh_pre_run_check(self, path: str = "") -> None:
        """Update PreRunCheckWidget for the merge input directory."""
        dir_path = path or self.input_dir.get_path()
        if not dir_path:
            self._pre_run_check.set_checks([])
            return
        self._pre_run_check.set_checks([
            FileCheck(
                label="Input directory",
                path=dir_path,
                required=True,
            )
        ])

    # -- Config building --------------------------------------------------

    def _build_config_dict(self) -> Dict[str, Any]:
        """Generate a YAML-compatible config dict from direct fields."""
        config: Dict[str, Any] = dict(self._loaded_config) if self._loaded_config else {}

        # Testing period metadata
        fy = self.fiscal_year.get_value()
        qtr = self.quarter.get_value()
        if fy or qtr:
            tp = config.setdefault("testing_period", {})
            if fy:
                tp["fiscal_year"] = fy
            if qtr:
                tp["quarter"] = qtr

        # Paths
        paths = config.setdefault("paths", {})
        input_dir = self.input_dir.get_path()
        if input_dir:
            paths["input_dir"] = input_dir

        # Processor
        proc = config.setdefault("processor", {})
        log_level = self.log_level.get_value()
        if log_level:
            proc["log_level"] = log_level

        # Options
        opts = config.setdefault("options", {})
        if self.dry_run.get_value():
            opts["dry_run"] = True
        if self.verbose.get_value():
            opts["verbose"] = True

        return config

    def _write_temp_config(self) -> str:
        """Write the merged config dict to a temp YAML file."""
        config = self._build_config_dict()
        fd, path = tempfile.mkstemp(suffix=".yaml", prefix="gui_merge_")
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            yaml.safe_dump(config, fh, default_flow_style=False)
        self._temp_config_path = path
        return path

    def _cleanup_temp_config(self) -> None:
        """Remove the temp config file if it exists."""
        if self._temp_config_path and os.path.isfile(self._temp_config_path):
            try:
                os.remove(self._temp_config_path)
            except OSError:
                pass
            self._temp_config_path = None

    # -- Argv building ----------------------------------------------------

    def build_argv(self) -> List[str]:
        """Build argv for the merge script."""
        argv: List[str] = ["--gui-mode"]

        # Generate temp config from direct fields
        config_path = self._write_temp_config()
        argv.extend(["--config", config_path])

        # Direct CLI overrides (the script also reads these independently)
        input_dir = self.input_dir.get_path()
        if input_dir:
            argv.extend(["--input-dir", input_dir])
        log_level = self.log_level.get_value()
        if log_level:
            argv.extend(["--log-level", log_level])
        if self.dry_run.get_value():
            argv.append("--dry-run")
        if self.verbose.get_value():
            argv.append("--verbose")
        return argv

    # -- Config population ------------------------------------------------

    def populate_from_config(self, config: Dict[str, Any]) -> None:
        """Fill direct fields from loaded YAML config."""
        self._loaded_config = config

        # Testing period
        tp = config.get("testing_period", {})
        if tp.get("fiscal_year"):
            self.fiscal_year.set_value(tp["fiscal_year"])
        if tp.get("quarter"):
            self.quarter.set_value(tp["quarter"])

        # Paths
        paths = config.get("paths", {})
        if paths.get("input_dir"):
            self.input_dir.set_path(str(paths["input_dir"]))

        # Processor
        proc = config.get("processor", {})
        if proc.get("log_level"):
            self.log_level.set_value(proc["log_level"])

        # Options
        opts = config.get("options", {})
        if opts.get("dry_run"):
            self.dry_run.set_value(True)
        if opts.get("verbose"):
            self.verbose.set_value(True)

    # -- Run / Cancel / Finished ------------------------------------------

    def _on_run(self) -> None:
        self._execute(dry_run=False)

    def _on_dry_run(self) -> None:
        self._execute(dry_run=True)

    def _execute(self, dry_run: bool = False) -> None:
        import importlib
        module = importlib.import_module("src.replay.merge_inconsistent_ids")
        argv = self.build_argv()
        if dry_run and "--dry-run" not in argv:
            argv.append("--dry-run")
        self.log_viewer.clear()
        self.log_viewer.append_line("[GUI] Running: replay-merge")
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
        success = exit_code == 0
        if success:
            self.log_viewer.append_line("[GUI] Completed successfully")
        else:
            self.log_viewer.append_error(f"[GUI] Finished with exit code {exit_code}")
        _update_last_run(self._last_run, self._pfx, success)
        self._cleanup_temp_config()
        self._worker = None


# ---------------------------------------------------------------------------
# Main Replay Tab
# ---------------------------------------------------------------------------

class ReplayTab(QWidget):
    """Replay Processing tab with sidebar navigation."""

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

        panels = [
            ("Phase II", BaseReplayPanel(
                "src.replay.phase_2_processor",
                "Phase II Processor",
                subtitle="Transaction reference lookup and correction matching",
                settings_prefix="phase2",
                extra_paths=[
                    {"label": "Input directory:", "key": "replay_input",
                     "tooltip": "Directory containing replay CSV/XLSX files."},
                    {"label": "Incident files directory:", "key": "incident_files",
                     "tooltip": "Directory containing incident code analysis CSVs."},
                    {"label": "Output directory:", "key": "replay_output",
                     "tooltip": "Directory for processed output files."},
                    {"label": "Log directory:", "key": "log_output",
                     "tooltip": "Directory for processing log files."},
                ],
                extra_file_patterns=[
                    {
                        "label": "Incident file pattern:",
                        "key": "incident_pattern",
                        "default": "FY25 Q4 *.csv",
                        "tooltip": "Glob pattern matching incident analysis CSVs, e.g. FY25 Q4 *.csv",
                        "is_list": False,
                    },
                ],
                default_incident_columns=_PHASE2_INCIDENT_COLUMNS,
            )),
            ("Phase III - Feedback", BaseReplayPanel(
                "src.replay.phase_3_processor",
                "Phase III - Feedback Processor",
                subtitle="Inconsistent ID and name matching processor",
                settings_prefix="phase3",
                extra_paths=[
                    {"label": "Input directory:", "key": "replay_input",
                     "tooltip": "Directory containing Phase III replay files."},
                    {"label": "Incident files directory:", "key": "incident_files",
                     "tooltip": "Directory containing incident code analysis CSVs."},
                    {"label": "Output directory:", "key": "replay_output",
                     "tooltip": "Directory for processed output files."},
                    {"label": "Log directory:", "key": "log_output",
                     "tooltip": "Directory for processing log files."},
                ],
                extra_file_patterns=[
                    {
                        "label": "Incident file pattern:",
                        "key": "incident_pattern",
                        "default": "FY25 Q4 *.csv",
                        "tooltip": "Glob pattern matching incident analysis CSVs, e.g. FY25 Q4 *.csv",
                        "is_list": False,
                    },
                    {
                        "label": "Replay file patterns:",
                        "key": "replay_patterns",
                        "default": "Replay_*_PHASE 3_Inconsistent_IDs_Summary_FINAL.csv, Replay_*_PHASE 3_Inconsistent_Names_Summary_FINAL.csv",
                        "tooltip": "Comma-separated glob patterns for Phase III replay input files.",
                        "placeholder": "Replay_*_Inconsistent_IDs_Summary_FINAL.csv, ...",
                        "is_list": True,
                    },
                ],
                default_incident_columns=_PHASE3_INCIDENT_COLUMNS,
            )),
            ("Phase III - Final Lookup", BaseReplayPanel(
                "src.replay.phase_3_final_lookup",
                "Phase III - Final Lookup Processor",
                subtitle="UnaVista manual corrections final lookup",
                settings_prefix="phase3_final",
                extra_paths=[
                    {"label": "Input directory:", "key": "replay_input",
                     "tooltip": "Directory containing Phase III output files."},
                    {"label": "UnaVista files directory:", "key": "unavista_files",
                     "tooltip": "Directory containing UnaVista manual corrections CSVs."},
                    {"label": "Output directory:", "key": "replay_output",
                     "tooltip": "Directory for final lookup output files."},
                    {"label": "Log directory:", "key": "log_output",
                     "tooltip": "Directory for processing log files."},
                ],
            )),
            ("Merge Summaries", MergeInconsistentPanel()),
        ]

        for label, panel in panels:
            self._sidebar.addItem(label)
            self._stack.addWidget(panel)

        self._sidebar.setCurrentRow(0)

    def _on_sidebar_changed(self, index: int) -> None:
        """Switch the visible panel."""
        self._stack.setCurrentIndex(index)

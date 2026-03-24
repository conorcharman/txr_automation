#!/usr/bin/env python3
"""
Replay Processing Tab
=====================

Four replay processing script panels:
- Phase 2 Processor
- Phase 3 Processor
- Phase 3 Final Lookup
- Merge Inconsistent Summaries

Uses a sidebar list + stacked widget layout with per-panel log viewers.
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


# ---------------------------------------------------------------------------
# Base replay panel (Phase 2 / Phase 3 style)
# ---------------------------------------------------------------------------

class BaseReplayPanel(QWidget):
    """Base panel for replay processor scripts.

    Provides config file, use-env checkbox, log level, and optional
    path override fields.
    """

    def __init__(
        self,
        script_module_path: str,
        title: str,
        extra_paths: Optional[List[Dict[str, str]]] = None,
        settings_prefix: str = "",
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._module_path = script_module_path
        self._worker: Optional[ScriptRunnerWorker] = None
        pfx = f"replay.{settings_prefix}" if settings_prefix else "replay"

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(f"<b>{title}</b>"))

        self.config_loader = ConfigLoaderWidget()
        self.config_loader.config_loaded.connect(self.populate_from_config)
        layout.addWidget(self.config_loader)

        self.use_env = FormFieldWidget(
            "Use Environment Vars", field_type="checkbox",
            tooltip="Load configuration from environment variables instead of YAML.",
            settings_key=f"{pfx}.use_env",
        )
        layout.addWidget(self.use_env)

        self.log_level = FormFieldWidget(
            "Log Level:", field_type="dropdown",
            choices=LOG_LEVELS, default="INFO",
            tooltip="Logging verbosity level.",
            settings_key=f"{pfx}.log_level",
        )
        layout.addWidget(self.log_level)

        # Optional path overrides
        self._path_pickers: Dict[str, FilePickerWidget] = {}
        if extra_paths:
            layout.addWidget(QLabel("Path Overrides (optional):"))
            for path_def in extra_paths:
                picker = FilePickerWidget(
                    path_def["label"], mode="directory",
                    tooltip=path_def.get("tooltip", ""),
                    settings_key=f"{pfx}.{path_def['key']}",
                )
                layout.addWidget(picker)
                self._path_pickers[path_def["key"]] = picker

        self.run_controls = RunControlsWidget()
        self.run_controls.run_clicked.connect(self._on_run)
        self.run_controls.cancel_clicked.connect(self._on_cancel)
        # Hide dry-run (replay scripts don't support it)
        self.run_controls._dry_run_btn.setVisible(False)
        layout.addWidget(self.run_controls)

        self.log_viewer = LogViewerWidget()
        layout.addWidget(self.log_viewer, stretch=1)

    def build_argv(self) -> List[str]:
        """Build argv for the replay processor."""
        argv: List[str] = []
        config_path = self.config_loader.get_last_path()
        if config_path:
            argv.extend(["--config", config_path])
        if self.use_env.get_value():
            argv.append("--use-env")
        log_level = self.log_level.get_value()
        if log_level:
            argv.extend(["--log-level", log_level])
        return argv

    def populate_from_config(self, config: Dict[str, Any]) -> None:
        """Fill path overrides from YAML config."""
        paths = config.get("paths", {})
        for key, picker in self._path_pickers.items():
            val = paths.get(key, "")
            if val:
                picker.set_path(str(val))

    def _on_run(self) -> None:
        module = _import_script(self._module_path)
        if module is None:
            self.log_viewer.append_error(
                f"Failed to import {self._module_path}"
            )
            return
        argv = self.build_argv()
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
        if exit_code == 0:
            self.log_viewer.append_line("[GUI] Completed successfully")
        else:
            self.log_viewer.append_error(
                f"[GUI] Finished with exit code {exit_code}"
            )
        self._worker = None


# ---------------------------------------------------------------------------
# Merge Inconsistent Summaries panel
# ---------------------------------------------------------------------------

class MergeInconsistentPanel(QWidget):
    """Panel for the merge-inconsistent-summaries script."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._worker: Optional[ScriptRunnerWorker] = None
        pfx = "replay.merge_inconsistent"

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("<b>Merge Inconsistent Summaries</b>"))

        self.config_loader = ConfigLoaderWidget()
        layout.addWidget(self.config_loader)

        self.input_dir = FilePickerWidget(
            "Input Directory:", mode="directory",
            tooltip="Directory containing inconsistent ID summary files.",
            settings_key=f"{pfx}.input_dir",
        )
        layout.addWidget(self.input_dir)

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

    def build_argv(self) -> List[str]:
        argv: List[str] = []
        config_path = self.config_loader.get_last_path()
        if config_path:
            argv.extend(["--config", config_path])
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

    def _on_run(self) -> None:
        self._execute(dry_run=False)

    def _on_dry_run(self) -> None:
        self._execute(dry_run=True)

    def _execute(self, dry_run: bool = False) -> None:
        module = _import_script("replay.merge_inconsistent_ids")
        if module is None:
            self.log_viewer.append_error(
                "Failed to import merge_inconsistent_ids"
            )
            return
        argv = self.build_argv()
        if dry_run and "--dry-run" not in argv:
            argv.append("--dry-run")
        self.log_viewer.clear()
        self.log_viewer.append_line(
            f"[GUI] Running: merge_inconsistent_ids {' '.join(argv)}"
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
            ("Phase 2 Processor", BaseReplayPanel(
                "replay.phase_2_processor",
                "Phase 2 Processor",
                settings_prefix="phase2",
                extra_paths=[
                    {"label": "Replay Input:", "key": "replay_input"},
                    {"label": "Incident Files:", "key": "incident_files"},
                    {"label": "Replay Output:", "key": "replay_output"},
                    {"label": "Log Output:", "key": "log_output"},
                ],
            )),
            ("Phase 3 Processor", BaseReplayPanel(
                "replay.phase_3_processor",
                "Phase 3 Processor",
                settings_prefix="phase3",
                extra_paths=[
                    {"label": "Replay Input:", "key": "replay_input"},
                    {"label": "Incident Files:", "key": "incident_files"},
                    {"label": "Replay Output:", "key": "replay_output"},
                    {"label": "Log Output:", "key": "log_output"},
                ],
            )),
            ("Phase 3 Final", BaseReplayPanel(
                "replay.phase_3_final_lookup",
                "Phase 3 Final Lookup",
                settings_prefix="phase3_final",
                extra_paths=[
                    {"label": "Replay Input:", "key": "replay_input"},
                    {"label": "Incident Files:", "key": "incident_files"},
                    {"label": "Replay Output:", "key": "replay_output"},
                    {"label": "UnaVista Files:", "key": "unavista_files"},
                    {"label": "Log Output:", "key": "log_output"},
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

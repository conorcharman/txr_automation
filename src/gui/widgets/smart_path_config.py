#!/usr/bin/env python3
"""
SmartPathConfigWidget
=====================

A composite widget that derives stage directories from a base
directory + fiscal period and displays live status badges and
CSV file counts for each stage.

Mirrors the web app's ``SmartPathConfig`` component.

Emits :attr:`paths_resolved` whenever the base directory or period
changes (triggered on ``editingFinished`` / focus-lost to avoid
spamming filesystem scans).

Usage:
    smart = SmartPathConfigWidget(settings_prefix="accuracy.validation")
    smart.paths_resolved.connect(self._on_paths_resolved)
    layout.addWidget(smart)

    # Drive period from a TestingPeriodWidget
    period_widget.period_changed.connect(smart.set_period)
"""

from __future__ import annotations

import os
from typing import Optional

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QFileDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from gui.utils.file_discovery_service import (
    FileDiscoveryService,
    PathStatus,
    SmartPaths,
)
from gui.utils.settings import settings


# Colour tokens for path-status labels (keeps theme consistent)
_COLOUR_FOUND = "#1A7F3C"     # green
_COLOUR_EMPTY = "#B8860B"     # amber
_COLOUR_MISSING = "#9E0025"   # AJ Bell red
_COLOUR_UNKNOWN = "#6A737B"   # grey


def _status_colour(status: PathStatus) -> str:
    return {
        PathStatus.FOUND: _COLOUR_FOUND,
        PathStatus.EMPTY: _COLOUR_EMPTY,
        PathStatus.MISSING: _COLOUR_MISSING,
    }.get(status, _COLOUR_UNKNOWN)


def _status_text(status: PathStatus, file_count: int) -> str:
    if status == PathStatus.FOUND:
        return f"✓  {file_count} CSV file{'s' if file_count != 1 else ''}"
    if status == PathStatus.EMPTY:
        return "⚠  Empty"
    return "✗  Missing"


# Stage labels shown in the grid
_STAGES = [
    ("extracts", "Extracts"),
    ("templates", "Templates"),
    ("output", "Output"),
    ("logs", "Logs"),
    ("kaizen", "Kaizen"),
]


class SmartPathConfigWidget(QWidget):
    """Base directory + period → resolved stage paths with live status.

    Args:
        settings_prefix: QSettings key prefix used to persist ``base_dir``.
        stages: Subset of stage keys to display.  Defaults to all five.
        parent: Parent widget.
    """

    paths_resolved = Signal(object)  # SmartPaths

    def __init__(
        self,
        settings_prefix: str = "accuracy",
        stages: Optional[list[str]] = None,
        module: Optional[str] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._prefix = settings_prefix
        self._base_key = f"{settings_prefix}.base_dir"
        self._svc = FileDiscoveryService()
        self._module = module
        self._fy = ""
        self._quarter = ""
        self._stages = stages or [s[0] for s in _STAGES]

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        group = QGroupBox("Smart Path Configuration")
        layout = QVBoxLayout(group)

        # --- Base directory row ---
        base_row = QHBoxLayout()
        base_row.addWidget(QLabel("Base directory:"))
        self._base_edit = QLineEdit()
        self._base_edit.setPlaceholderText("e.g. C:/data/txr")
        self._base_edit.setToolTip(
            "Root folder containing FY/Q sub-directories.\n"
            "Stage paths are resolved automatically."
        )
        self._base_edit.editingFinished.connect(self._on_base_finished)
        base_row.addWidget(self._base_edit, stretch=1)

        browse_btn = QPushButton("Browse…")
        browse_btn.setFixedWidth(80)
        browse_btn.clicked.connect(self._on_browse)
        base_row.addWidget(browse_btn)
        layout.addLayout(base_row)

        # --- Status grid (stage label | path | badge) ---
        self._grid = QGridLayout()
        self._grid.setColumnStretch(1, 1)
        self._path_labels: dict[str, QLabel] = {}
        self._status_labels: dict[str, QLabel] = {}

        visible_stages = [(k, lbl) for k, lbl in _STAGES if k in self._stages]
        for row, (key, label) in enumerate(visible_stages):
            name_lbl = QLabel(f"  {label}:")
            name_lbl.setStyleSheet("color: #6A737B; font-size: 10pt;")
            self._grid.addWidget(name_lbl, row, 0)

            path_lbl = QLabel("—")
            path_lbl.setStyleSheet("color: #6A737B; font-size: 10pt;")
            path_lbl.setWordWrap(False)
            self._path_labels[key] = path_lbl
            self._grid.addWidget(path_lbl, row, 1)

            status_lbl = QLabel("")
            status_lbl.setFixedWidth(140)
            status_lbl.setStyleSheet(f"color: {_COLOUR_UNKNOWN}; font-size: 10pt;")
            self._status_labels[key] = status_lbl
            self._grid.addWidget(status_lbl, row, 2)

        layout.addLayout(self._grid)
        outer.addWidget(group)

        # Restore persisted base dir
        saved = settings.load(self._base_key, "")
        if saved:
            self._base_edit.setText(str(saved))

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def set_period(self, fiscal_year: str, quarter: str) -> None:
        """Update the fiscal period and refresh resolved paths.

        Args:
            fiscal_year: e.g. ``"FY26"``.
            quarter: e.g. ``"Q1"``.
        """
        self._fy = fiscal_year
        self._quarter = quarter
        self._refresh()

    @property
    def base_dir(self) -> str:
        """The currently entered base directory."""
        return self._base_edit.text().strip()

    def get_smart_paths(self) -> Optional[SmartPaths]:
        """Return the most recently resolved :class:`SmartPaths`, or ``None``."""
        return self._last_paths if hasattr(self, "_last_paths") else None

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _on_base_finished(self) -> None:
        """Triggered when the user leaves the base directory field."""
        base = self._base_edit.text().strip()
        if base:
            settings.save(self._base_key, base)
        self._refresh()

    def _on_browse(self) -> None:
        path = QFileDialog.getExistingDirectory(
            self, "Select Base Directory", self._base_edit.text()
        )
        if path:
            self._base_edit.setText(path)
            settings.save(self._base_key, path)
            self._refresh()

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _refresh(self) -> None:
        """Resolve paths and update the status grid."""
        base = self._base_edit.text().strip()
        if not base or not self._fy or not self._quarter:
            self._clear_grid()
            return

        paths = self._svc.resolve_smart_paths(
            base, self._fy, self._quarter, module=self._module
        )
        self._last_paths = paths  # type: ignore[attr-defined]
        self._update_grid(paths)
        self.paths_resolved.emit(paths)

    def _update_grid(self, paths: SmartPaths) -> None:
        for key in self._stages:
            stage_path = getattr(paths, key, "")
            status = paths.statuses.get(key, PathStatus.MISSING)
            count = paths.file_counts.get(key, 0)

            path_lbl = self._path_labels.get(key)
            if path_lbl:
                # Show the last 2 path components to keep it readable
                parts = stage_path.replace("\\", "/").split("/")
                short = "/".join(parts[-3:]) if len(parts) > 3 else stage_path
                path_lbl.setText(short)
                path_lbl.setToolTip(stage_path)

            status_lbl = self._status_labels.get(key)
            if status_lbl:
                colour = _status_colour(status)
                text = _status_text(status, count)
                status_lbl.setText(text)
                status_lbl.setStyleSheet(f"color: {colour}; font-size: 10pt;")

    def _clear_grid(self) -> None:
        for lbl in self._path_labels.values():
            lbl.setText("—")
        for lbl in self._status_labels.values():
            lbl.setText("")
            lbl.setStyleSheet(f"color: {_COLOUR_UNKNOWN}; font-size: 10pt;")

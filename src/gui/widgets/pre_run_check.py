#!/usr/bin/env python3
"""
PreRunCheckWidget
=================

A compact pre-flight table that verifies required files exist
before allowing the Run button to be enabled.

Shows a row per file with:
- A short label
- The filename (basename only, full path on hover)
- A coloured status badge (✓ / ✗)

The :attr:`all_required_present` property returns ``True`` only
when every required file exists.

Usage:
    checks = [
        FileCheck("Extract (7_37)", "/data/.../7_37_FY26_Q1_extract.csv", required=True),
        FileCheck("Template (7_37)", "/data/.../FY26 Q1 7_37.csv", required=False),
    ]
    pre_run = PreRunCheckWidget()
    pre_run.set_checks(checks)
    pre_run.status_changed.connect(run_controls.set_run_enabled)
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import List, Optional

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)


# ---------------------------------------------------------------------------
# Data class
# ---------------------------------------------------------------------------


@dataclass
class FileCheck:
    """A single file to check before running.

    Args:
        label: Short human-readable label, e.g. ``"Extract (7_37)"``.
        path: Full filesystem path to check.
        required: Whether the file must exist for the run to proceed.
    """

    label: str
    path: str
    required: bool = True


# ---------------------------------------------------------------------------
# Widget
# ---------------------------------------------------------------------------

_COLOUR_OK = "#1A7F3C"
_COLOUR_WARN = "#B8860B"
_COLOUR_ERR = "#9E0025"
_COLOUR_GREY = "#6A737B"


class PreRunCheckWidget(QWidget):
    """Compact pre-flight file check table.

    Emits :attr:`status_changed` with ``True`` when all required
    files are present, ``False`` otherwise.
    """

    status_changed = Signal(bool)  # all_required_present

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._checks: List[FileCheck] = []

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        self._header = QLabel("Pre-run checks")
        self._header.setStyleSheet("font-weight: bold; font-size: 10pt;")
        outer.addWidget(self._header)

        frame = QFrame()
        frame.setFrameShape(QFrame.Shape.StyledPanel)
        frame.setStyleSheet(
            "QFrame { border: 1px solid #E0E0E0; border-radius: 4px; "
            "background: #F9F9F9; padding: 2px; }"
        )
        self._grid = QGridLayout(frame)
        self._grid.setColumnStretch(1, 1)
        self._grid.setContentsMargins(6, 4, 6, 4)
        self._grid.setVerticalSpacing(2)
        outer.addWidget(frame)

        self._summary = QLabel("")
        self._summary.setStyleSheet("font-size: 10pt; margin-top: 2px;")
        outer.addWidget(self._summary)

        self.setVisible(False)  # Hidden until checks are set

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def set_checks(self, checks: List[FileCheck]) -> None:
        """Populate the table with *checks* and refresh statuses.

        Args:
            checks: List of :class:`FileCheck` to display.
        """
        self._checks = checks
        self._rebuild()
        self.setVisible(bool(checks))

    def refresh(self) -> None:
        """Re-stat all files and update the display."""
        self._rebuild()

    @property
    def all_required_present(self) -> bool:
        """``True`` if every required :class:`FileCheck` path exists."""
        return all(
            os.path.isfile(c.path) for c in self._checks if c.required
        )

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _rebuild(self) -> None:
        """Clear and repopulate the grid."""
        # Remove existing row widgets
        while self._grid.count():
            item = self._grid.takeAt(0)
            if item and item.widget():
                item.widget().deleteLater()

        ok_count = 0
        required_ok = 0
        required_total = 0

        for row, check in enumerate(self._checks):
            exists = os.path.isfile(check.path)
            if exists:
                ok_count += 1
            if check.required:
                required_total += 1
                if exists:
                    required_ok += 1

            # Label
            label_lbl = QLabel(check.label)
            label_lbl.setStyleSheet("font-size: 10pt; color: #1A1A1A;")
            self._grid.addWidget(label_lbl, row, 0)

            # Path (basename, full on tooltip)
            basename = os.path.basename(check.path) if check.path else "—"
            path_lbl = QLabel(basename)
            path_lbl.setStyleSheet("font-size: 10pt; color: #6A737B;")
            path_lbl.setToolTip(check.path)
            self._grid.addWidget(path_lbl, row, 1)

            # Status badge
            if exists:
                status_text = "✓ Found"
                colour = _COLOUR_OK
            elif check.required:
                status_text = "✗ Missing"
                colour = _COLOUR_ERR
            else:
                status_text = "– Optional"
                colour = _COLOUR_WARN

            status_lbl = QLabel(status_text)
            status_lbl.setFixedWidth(90)
            status_lbl.setStyleSheet(f"font-size: 10pt; color: {colour};")
            self._grid.addWidget(status_lbl, row, 2)

        # Summary line
        all_ok = required_ok == required_total
        if not self._checks:
            self._summary.setText("")
        elif all_ok:
            self._summary.setText(
                f"<span style='color:{_COLOUR_OK};'>All required files found</span>"
            )
        else:
            missing = required_total - required_ok
            self._summary.setText(
                f"<span style='color:{_COLOUR_ERR};'>"
                f"{missing} required file{'s' if missing != 1 else ''} missing — "
                f"Run button disabled</span>"
            )

        self.status_changed.emit(all_ok)

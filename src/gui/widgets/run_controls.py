#!/usr/bin/env python3
"""
RunControlsWidget
=================

Run, Cancel, and Dry Run buttons with a progress indicator.
Toggles between running and idle states.
"""

from typing import Optional

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QProgressBar,
    QPushButton,
    QWidget,
)


class RunControlsWidget(QWidget):
    """Script execution controls."""

    run_clicked = Signal()
    dry_run_clicked = Signal()
    cancel_clicked = Signal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._run_btn = QPushButton("Run")
        self._run_btn.setFixedWidth(80)
        self._run_btn.clicked.connect(self.run_clicked.emit)
        layout.addWidget(self._run_btn)

        self._dry_run_btn = QPushButton("Dry Run")
        self._dry_run_btn.setFixedWidth(80)
        self._dry_run_btn.clicked.connect(self.dry_run_clicked.emit)
        layout.addWidget(self._dry_run_btn)

        self._cancel_btn = QPushButton("Cancel")
        self._cancel_btn.setFixedWidth(80)
        self._cancel_btn.setEnabled(False)
        self._cancel_btn.clicked.connect(self.cancel_clicked.emit)
        layout.addWidget(self._cancel_btn)

        self._progress = QProgressBar()
        self._progress.setVisible(False)
        self._progress.setMaximum(0)  # Indeterminate by default
        layout.addWidget(self._progress, stretch=1)

        layout.addStretch()

    def set_running(self, running: bool) -> None:
        """Toggle button states for running/idle."""
        self._run_btn.setEnabled(not running)
        self._dry_run_btn.setEnabled(not running)
        self._cancel_btn.setEnabled(running)
        self._progress.setVisible(running)

    def set_progress(self, value: int, maximum: int = 0) -> None:
        """Update the progress bar. maximum=0 means indeterminate."""
        self._progress.setMaximum(maximum)
        self._progress.setValue(value)

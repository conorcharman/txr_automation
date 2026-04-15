#!/usr/bin/env python3
"""
Status Badge Widget
===================

A small coloured label that displays a job or schedule status string.
Uses QSS object-name styling to pick up badge colours from the theme.

Supported statuses: ``pending``, ``running``, ``waiting``, ``success``,
``failed``, ``cancelled``, ``never_run``.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel


class StatusBadgeWidget(QLabel):
    """Compact badge showing a job/schedule status with colour coding."""

    def __init__(self, status: str = "", parent=None) -> None:
        super().__init__(parent)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        if status:
            self.set_status(status)

    def set_status(self, status: str) -> None:
        """Update the badge text and apply the matching QSS object name.

        Args:
            status: One of ``"pending"``, ``"running"``, ``"waiting"``,
                ``"success"``, ``"failed"``, ``"cancelled"``, ``"never_run"``.
        """
        display = status.replace("_", " ").capitalize()
        self.setText(display)
        self.setObjectName(f"badge-{status}")
        # Force QSS re-evaluation after objectName change.
        self.style().unpolish(self)
        self.style().polish(self)

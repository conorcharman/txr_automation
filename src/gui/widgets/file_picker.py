#!/usr/bin/env python3
"""
FilePickerWidget
================

A file or directory selection widget with a native dialog.
Provides a label, read-only line edit, and Browse button.
"""

from typing import Optional

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QWidget,
)

from gui.constants import CSV_FILTER
from gui.utils.settings import settings


class FilePickerWidget(QWidget):
    """File or directory selection widget with native dialog."""

    path_changed = Signal(str)

    def __init__(
        self,
        label: str,
        mode: str = "file",
        file_filter: str = CSV_FILTER,
        tooltip: str = "",
        placeholder: str = "",
        settings_key: str = "",
        parent: Optional[QWidget] = None,
    ) -> None:
        """
        Initialise the file picker widget.

        Args:
            label: Display label for the field.
            mode: One of "file", "directory", or "save".
            file_filter: File dialog filter string.
            tooltip: Hover tooltip text for the label and line edit.
            placeholder: Placeholder text shown when no file is selected.
            settings_key: QSettings key for persisting the path.
            parent: Parent widget.
        """
        super().__init__(parent)
        self._mode = mode
        self._filter = file_filter
        self._settings_key = settings_key

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._label = QLabel(label)
        self._label.setFixedWidth(140)
        layout.addWidget(self._label)

        self._line_edit = QLineEdit()
        self._line_edit.setReadOnly(True)
        self._line_edit.setPlaceholderText(placeholder or "No file selected")
        layout.addWidget(self._line_edit, stretch=1)

        self._browse_btn = QPushButton("Browse\u2026")
        self._browse_btn.setFixedWidth(80)
        self._browse_btn.clicked.connect(self._on_browse)
        layout.addWidget(self._browse_btn)

        if tooltip:
            self._label.setToolTip(tooltip)
            self._line_edit.setToolTip(tooltip)

        # Restore persisted path
        if self._settings_key:
            saved = settings.load(self._settings_key, "")
            if saved:
                self._line_edit.setText(str(saved))
            self.path_changed.connect(self._persist_path)

    def _on_browse(self) -> None:
        """Open the native file dialog based on mode."""
        path = ""
        if self._mode == "file":
            path, _ = QFileDialog.getOpenFileName(
                self, f"Select {self._label.text()}", "", self._filter
            )
        elif self._mode == "directory":
            path = QFileDialog.getExistingDirectory(
                self, f"Select {self._label.text()}"
            )
        elif self._mode == "save":
            path, _ = QFileDialog.getSaveFileName(
                self, f"Save {self._label.text()}", "", self._filter
            )

        if path:
            self._line_edit.setText(path)
            self.path_changed.emit(path)

    def get_path(self) -> str:
        """Return the currently selected path."""
        return self._line_edit.text()

    def set_path(self, path: str) -> None:
        """Set the path programmatically."""
        self._line_edit.setText(path)
        self.path_changed.emit(path)

    def clear(self) -> None:
        """Clear the selected path."""
        self._line_edit.clear()

    def set_enabled(self, enabled: bool) -> None:
        """Enable or disable the browse button."""
        self._browse_btn.setEnabled(enabled)
        self._line_edit.setEnabled(enabled)

    def _persist_path(self, path: str) -> None:
        """Save the current path to QSettings."""
        if self._settings_key:
            settings.save(self._settings_key, path)

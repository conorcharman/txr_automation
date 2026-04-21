#!/usr/bin/env python3
"""
FilePickerWidget
================

A file or directory selection widget with a native dialog.
Provides a label, read-only line edit, Browse button, and an optional
Auto-detect button that presents filesystem candidates ranked by
modification time.
"""

from typing import Callable, List, Optional

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from gui.constants import CSV_FILTER
from gui.utils.settings import settings


class _CandidateDialog(QDialog):
    """Modal candidate-picker dialog for auto-detect results."""

    def __init__(self, candidates: list, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Auto-detect — select a file")
        self.setMinimumWidth(520)
        self._selected_path = ""

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Candidates found (newest first):"))

        self._list = QListWidget()
        for cand in candidates:
            text = f"{cand.filename}  ({cand.mtime_label}, {cand.size_label})"
            item = QListWidgetItem(text)
            item.setData(256, cand.path)  # Qt.UserRole
            self._list.addItem(item)
        if self._list.count():
            self._list.setCurrentRow(0)
        self._list.itemDoubleClicked.connect(self._on_double_click)
        layout.addWidget(self._list)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_ok)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _on_ok(self) -> None:
        item = self._list.currentItem()
        if item:
            self._selected_path = item.data(256)
        self.accept()

    def _on_double_click(self, item: QListWidgetItem) -> None:
        self._selected_path = item.data(256)
        self.accept()

    @property
    def selected_path(self) -> str:
        return self._selected_path


class FilePickerWidget(QWidget):
    """File or directory selection widget with native dialog.

    When *auto_detect_fn* is provided an **Auto-detect** button is
    shown.  Clicking it invokes the callable (which must return a list
    of :class:`~gui.utils.file_discovery_service.FileCandidate`
    objects) and presents a ranked candidate dialog.
    """

    path_changed = Signal(str)

    def __init__(
        self,
        label: str,
        mode: str = "file",
        file_filter: str = CSV_FILTER,
        tooltip: str = "",
        placeholder: str = "",
        settings_key: str = "",
        auto_detect_fn: Optional[Callable[[], List]] = None,
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
            auto_detect_fn: Zero-argument callable returning a list of
                ``FileCandidate`` objects.  When supplied, an
                **Auto-detect** button is shown alongside Browse.
            parent: Parent widget.
        """
        super().__init__(parent)
        self._mode = mode
        self._filter = file_filter
        self._settings_key = settings_key
        self._auto_detect_fn = auto_detect_fn

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._label = QLabel(label)
        self._label.setFixedWidth(140)
        layout.addWidget(self._label)

        self._line_edit = QLineEdit()
        self._line_edit.setReadOnly(True)
        self._line_edit.setPlaceholderText(placeholder or "No file selected")
        layout.addWidget(self._line_edit, stretch=1)

        if auto_detect_fn is not None:
            self._auto_btn = QPushButton("Auto-detect")
            self._auto_btn.setFixedWidth(90)
            self._auto_btn.setToolTip(
                "Scan the configured directory for matching files\n"
                "and pick the most recent candidate."
            )
            self._auto_btn.clicked.connect(self._on_auto_detect)
            layout.addWidget(self._auto_btn)
        else:
            self._auto_btn = None  # type: ignore[assignment]

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

    def _on_auto_detect(self) -> None:
        """Run auto_detect_fn, show a candidate dialog, and update the path."""
        if self._auto_detect_fn is None:
            return
        if self._auto_btn is not None:
            self._auto_btn.setEnabled(False)
            self._auto_btn.setText("Scanning…")
        try:
            candidates = self._auto_detect_fn()
        except Exception:
            candidates = []
        finally:
            if self._auto_btn is not None:
                self._auto_btn.setEnabled(True)
                self._auto_btn.setText("Auto-detect")

        if not candidates:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.information(
                self,
                "Auto-detect",
                "No matching files found in the configured directory.",
            )
            return

        dlg = _CandidateDialog(candidates, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted and dlg.selected_path:
            self._line_edit.setText(dlg.selected_path)
            self.path_changed.emit(dlg.selected_path)

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
        """Enable or disable the browse (and auto-detect) button."""
        self._browse_btn.setEnabled(enabled)
        self._line_edit.setEnabled(enabled)
        if self._auto_btn is not None:
            self._auto_btn.setEnabled(enabled)

    def _persist_path(self, path: str) -> None:
        """Save the current path to QSettings."""
        if self._settings_key:
            settings.save(self._settings_key, path)

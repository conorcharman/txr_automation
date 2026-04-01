#!/usr/bin/env python3
"""
LogViewerWidget
===============

Read-only log output display with monospace font, auto-scrolling,
colour-coded error lines, and a Clear button.
"""

from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QTextCharFormat, QColor
from PySide6.QtWidgets import (
    QHBoxLayout,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from gui.constants import COLOUR_RED, LOG_FONT_FAMILY, LOG_FONT_SIZE, COLOUR_RED


class LogViewerWidget(QWidget):
    """Real-time log output display."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Log text area
        self._text_edit = QPlainTextEdit()
        self._text_edit.setReadOnly(True)
        self._text_edit.setFont(QFont(LOG_FONT_FAMILY, LOG_FONT_SIZE))
        self._text_edit.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        layout.addWidget(self._text_edit, stretch=1)

        # Button bar
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self._save_btn = QPushButton("Save Log…")
        self._save_btn.clicked.connect(self._on_save)
        btn_layout.addWidget(self._save_btn)

        self._clear_btn = QPushButton("Clear")
        self._clear_btn.clicked.connect(self.clear)
        btn_layout.addWidget(self._clear_btn)

        layout.addLayout(btn_layout)

        # Formats for normal and error text
        self._normal_fmt = QTextCharFormat()
        self._error_fmt = QTextCharFormat()
        self._error_fmt.setForeground(QColor(COLOUR_RED))

    def append_line(self, text: str) -> None:
        """Append a line of normal log output."""
        self._text_edit.appendPlainText(text.rstrip("\n"))
        self._auto_scroll()

    def append_error(self, text: str) -> None:
        """Append a line in red to indicate an error."""
        cursor = self._text_edit.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        cursor.insertText(text.rstrip("\n") + "\n", self._error_fmt)
        self._auto_scroll()

    def _auto_scroll(self) -> None:
        """Scroll to the bottom of the log."""
        scrollbar = self._text_edit.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def clear(self) -> None:
        """Clear all log output."""
        self._text_edit.clear()

    def get_text(self) -> str:
        """Return the full log text."""
        return self._text_edit.toPlainText()

    def _on_save(self) -> None:
        """Save log contents to a file."""
        from PySide6.QtWidgets import QFileDialog

        path, _ = QFileDialog.getSaveFileName(
            self, "Save Log", "", "Text Files (*.txt);;Log Files (*.log);;All Files (*)"
        )
        if path:
            self.save_to_file(path)

    def save_to_file(self, path: str) -> None:
        """Write log contents to the given path."""
        Path(path).write_text(self.get_text(), encoding="utf-8")

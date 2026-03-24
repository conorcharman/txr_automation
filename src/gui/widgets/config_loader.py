#!/usr/bin/env python3
"""
ConfigLoaderWidget
==================

Load and save YAML configuration files. Emits parsed dictionaries
via Qt signals so tab panels can populate their form fields.
"""

from pathlib import Path
from typing import Any, Dict, Optional

import yaml
from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QWidget,
)

from gui.constants import YAML_FILTER


class ConfigLoaderWidget(QWidget):
    """Load and save YAML configuration files."""

    config_loaded = Signal(dict)
    config_saved = Signal(str)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._last_path = ""

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        label = QLabel("Config File:")
        label.setFixedWidth(140)
        layout.addWidget(label)

        self._path_edit = QLineEdit()
        self._path_edit.setReadOnly(True)
        self._path_edit.setPlaceholderText("No config loaded")
        layout.addWidget(self._path_edit, stretch=1)

        self._load_btn = QPushButton("Load")
        self._load_btn.setFixedWidth(60)
        self._load_btn.clicked.connect(self._on_load)
        layout.addWidget(self._load_btn)

        self._save_btn = QPushButton("Save")
        self._save_btn.setFixedWidth(60)
        self._save_btn.clicked.connect(self._on_save_clicked)
        layout.addWidget(self._save_btn)

        self._pending_save_config: Optional[Dict[str, Any]] = None

    def _on_load(self) -> None:
        """Open a YAML file and emit the parsed config."""
        path, _ = QFileDialog.getOpenFileName(
            self, "Load Configuration", "", YAML_FILTER
        )
        if not path:
            return

        try:
            with open(path, "r", encoding="utf-8") as f:
                config = yaml.safe_load(f) or {}
            self._last_path = path
            self._path_edit.setText(path)
            self.config_loaded.emit(config)
        except Exception as e:
            QMessageBox.warning(
                self, "Config Error", f"Failed to load config:\n{e}"
            )

    def _on_save_clicked(self) -> None:
        """Signal that a save was requested. The parent panel must
        call save_config() with the current form state."""
        if self._pending_save_config is not None:
            self._do_save(self._pending_save_config)

    def save_config(self, config: Dict[str, Any]) -> None:
        """Save configuration dictionary to a YAML file."""
        if self._last_path:
            default_path = self._last_path
        else:
            default_path = ""

        path, _ = QFileDialog.getSaveFileName(
            self, "Save Configuration", default_path, YAML_FILTER
        )
        if not path:
            return

        self._do_save(config, path)

    def _do_save(
        self, config: Dict[str, Any], path: Optional[str] = None
    ) -> None:
        """Write config dict to YAML file."""
        save_path = path or self._last_path
        if not save_path:
            return

        try:
            Path(save_path).parent.mkdir(parents=True, exist_ok=True)
            with open(save_path, "w", encoding="utf-8") as f:
                yaml.dump(config, f, default_flow_style=False, sort_keys=False)
            self._last_path = save_path
            self._path_edit.setText(save_path)
            self.config_saved.emit(save_path)
        except Exception as e:
            QMessageBox.warning(
                self, "Save Error", f"Failed to save config:\n{e}"
            )

    def get_last_path(self) -> str:
        """Return the path of the last loaded/saved config."""
        return self._last_path

    def set_path(self, path: str) -> None:
        """Set the config path display without loading."""
        self._last_path = path
        self._path_edit.setText(path)

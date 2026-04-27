#!/usr/bin/env python3
"""
IncidentFileTableWidget
=======================

Table widget showing per-incident file paths (input, template, output)
with Browse buttons in each cell.  Auto-populates paths from a naming
convention when base directories and testing period are set.

Mirrors the web app's ``IncidentFileTable`` component.
"""

import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)


class _PathCell(QWidget):
    """Line edit + Browse button packed into a single cell widget."""

    path_changed = Signal(str)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(2, 0, 2, 0)
        layout.setSpacing(2)

        self._edit = QLineEdit()
        self._edit.setReadOnly(False)
        self._edit.textChanged.connect(self.path_changed.emit)
        layout.addWidget(self._edit, stretch=1)

        self._btn = QPushButton("...")
        self._btn.setFixedWidth(28)
        self._btn.setFixedHeight(22)
        self._btn.clicked.connect(self._browse)
        layout.addWidget(self._btn)

    def get_path(self) -> str:
        """Return the current path text."""
        return self._edit.text().strip()

    def set_path(self, path: str) -> None:
        """Set the path without emitting path_changed redundantly."""
        self._edit.blockSignals(True)
        self._edit.setText(path)
        self._edit.blockSignals(False)

    def _browse(self) -> None:
        """Open a native file dialog to pick a CSV file."""
        path, _ = QFileDialog.getOpenFileName(
            self, "Select CSV file", self.get_path(),
            "CSV Files (*.csv);;All Files (*)",
        )
        if path:
            self._edit.setText(path)


class IncidentFileTableWidget(QWidget):
    """Editable table mapping incident codes to input/template/output paths.

    Signals:
        configs_changed — emitted whenever any path is edited.
    """

    configs_changed = Signal()

    # Column indices
    COL_CODE = 0
    COL_INPUT = 1
    COL_TEMPLATE = 2
    COL_OUTPUT = 3

    def __init__(
        self,
        show_template: bool = True,
        collapsible: bool = True,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._show_template = show_template
        self._rows: List[Dict[str, Any]] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        if collapsible:
            self._toggle_btn = QPushButton("\u25b6 Incident File Paths")
            self._toggle_btn.setFlat(True)
            self._toggle_btn.setStyleSheet("text-align: left; padding: 2px;")
            self._toggle_btn.clicked.connect(self._toggle)
            layout.addWidget(self._toggle_btn)
        else:
            self._toggle_btn = None

        self._container = QWidget()
        container_layout = QVBoxLayout(self._container)
        container_layout.setContentsMargins(0, 0, 0, 0)

        # Build columns
        headers = ["Incident Code", "Input File"]
        if show_template:
            headers.append("Template File")
        headers.append("Output File")

        self._table = QTableWidget(0, len(headers))
        self._table.setHorizontalHeaderLabels(headers)
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.ResizeToContents
        )
        self._table.verticalHeader().setVisible(False)
        self._table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        container_layout.addWidget(self._table)

        layout.addWidget(self._container)

        if collapsible:
            self._container.setVisible(False)

    def _toggle(self) -> None:
        """Toggle visibility of the table."""
        visible = not self._container.isVisible()
        self._container.setVisible(visible)
        if self._toggle_btn:
            self._toggle_btn.setText(
                "\u25bc Incident File Paths" if visible
                else "\u25b6 Incident File Paths"
            )

    def set_incidents(
        self,
        incidents: List[Tuple[str, str]],
        extracts_dir: str = "",
        templates_dir: str = "",
        output_dir: str = "",
        fiscal_year: str = "",
        quarter: str = "",
    ) -> None:
        """Populate the table with one row per incident, auto-filling paths.

        Args:
            incidents: List of ``(incident_code, script_key)`` tuples.
            extracts_dir: Base directory for input extract CSVs.
            templates_dir: Base directory for template CSVs.
            output_dir: Base directory for output CSVs.
            fiscal_year: e.g. ``"FY26"``.
            quarter: e.g. ``"Q1"``.
        """
        self._table.setRowCount(0)
        self._rows.clear()

        for code, script_key in incidents:
            row_idx = self._table.rowCount()
            self._table.insertRow(row_idx)

            # Code column (read-only label)
            code_item = QTableWidgetItem(code)
            code_item.setFlags(code_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self._table.setItem(row_idx, self.COL_CODE, code_item)

            # Input path
            input_cell = _PathCell()
            if extracts_dir and fiscal_year and quarter:
                input_cell.set_path(
                    self._build_path(extracts_dir, code, fiscal_year, quarter, "extract.csv")
                )
            input_cell.path_changed.connect(lambda _: self.configs_changed.emit())

            col = 1
            self._table.setCellWidget(row_idx, col, input_cell)
            col += 1

            # Template path (optional)
            template_cell: Optional[_PathCell] = None
            if self._show_template:
                template_cell = _PathCell()
                if templates_dir and fiscal_year and quarter:
                    template_cell.set_path(
                        self._build_path(templates_dir, code, fiscal_year, quarter, "template.csv")
                    )
                template_cell.path_changed.connect(lambda _: self.configs_changed.emit())
                self._table.setCellWidget(row_idx, col, template_cell)
                col += 1

            # Output path — uses validated_{fy}_{q}_{code}.csv convention
            output_cell = _PathCell()
            if output_dir and fiscal_year and quarter:
                output_cell.set_path(
                    os.path.join(output_dir, f"validated_{fiscal_year}_{quarter}_{code}.csv")
                )
            output_cell.path_changed.connect(lambda _: self.configs_changed.emit())
            self._table.setCellWidget(row_idx, col, output_cell)

            self._rows.append({
                "code": code,
                "script_key": script_key,
                "input": input_cell,
                "template": template_cell,
                "output": output_cell,
            })

        # Resize rows to fit cell widgets
        self._table.resizeRowsToContents()

    def populate_from_discovery(
        self,
        results: List[Dict[str, Any]],
        script_key_map: Dict[str, str],
    ) -> None:
        """Fill input paths from API discovery results.

        Args:
            results: List of ``{"incidentCode": str, "filePath": str}`` dicts.
            script_key_map: Maps incident code to script key.
        """
        path_by_code: Dict[str, str] = {}
        for r in results:
            code = r.get("incidentCode", "")
            path = r.get("filePath", "")
            if code and path:
                path_by_code[code] = path

        for row in self._rows:
            code = row["code"]
            if code in path_by_code:
                row["input"].set_path(path_by_code[code])

    def get_configs(self) -> List[Dict[str, str]]:
        """Return the current file path configuration for each incident.

        Returns:
            List of dicts with keys ``scriptKey``, ``incidentCode``,
            ``inputFile``, ``templateFile``, ``outputFile``.
        """
        configs: List[Dict[str, str]] = []
        for row in self._rows:
            config: Dict[str, str] = {
                "scriptKey": row["script_key"],
                "incidentCode": row["code"],
                "inputFile": row["input"].get_path(),
                "outputFile": row["output"].get_path(),
            }
            if row["template"] is not None:
                config["templateFile"] = row["template"].get_path()
            configs.append(config)
        return configs

    @staticmethod
    def _build_path(
        base_dir: str, code: str, fy: str, q: str, suffix: str
    ) -> str:
        """Build a file path from the naming convention."""
        filename = f"{code}_{fy}_{q}_{suffix}"
        return os.path.join(base_dir, filename)
